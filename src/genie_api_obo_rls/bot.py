"""
Teams Bot integration with Databricks Genie API.

This module contains the Bot Framework adapter and message handler.

Features:
- Natural language queries to Databricks Genie
- OBO token exchange for user identity preservation (RLS)
- Auto-generated charts with type selection
- CSV/PNG download capabilities
"""

from __future__ import annotations

import asyncio
import base64
import sys
import traceback
from typing import Any

from aiohttp import web

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    TurnContext,
    UserState,
)
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.dialogs import DialogSet, DialogTurnStatus
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
    InvokeResponse,
)

from .auth import (
    TeamsSsoDialog,
    TokenCache,
    TokenExchangeError,
    exchange_aad_for_databricks_token_async,
    get_token_from_context,
    sign_out_user,
)
from .config import BotSettings, Settings
from .genie import GenieClient
from .charts import (
    ChartType,
    ChartData,
    analyze_data_for_chart,
    generate_chart,
    export_to_csv,
    get_chart_type_options,
)


# =============================================================================
# Bot Framework Adapter
# =============================================================================

def create_adapter(settings: BotSettings) -> BotFrameworkAdapter:
    """Create and configure the Bot Framework adapter."""
    # For Single Tenant, channel_auth_tenant must be set
    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.microsoft_app_id,
        app_password=settings.microsoft_app_password,
        channel_auth_tenant=settings.microsoft_app_tenant_id or None,
    )
    adapter = BotFrameworkAdapter(adapter_settings)

    async def on_error(context: TurnContext, error: Exception) -> None:
        print(f"[on_turn_error] unhandled error: {error}", file=sys.stderr)
        traceback.print_exc()
        await context.send_activity("Sorry, something went wrong processing your request.")

    adapter.on_turn_error = on_error
    return adapter


def create_bot_app(bot: "GenieBot", settings: BotSettings | None = None) -> web.Application:
    """Create the aiohttp web application with bot routes."""
    if settings is None:
        settings = BotSettings()

    adapter = create_adapter(settings)

    async def messages(request: web.Request) -> web.Response:
        """Handle incoming Bot Framework messages at /api/messages."""
        if "application/json" not in request.headers.get("Content-Type", ""):
            return web.Response(status=415)

        body = await request.json()
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")

        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        if response:
            return web.json_response(data=response.body, status=response.status)
        return web.Response(status=201)

    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/healthz", lambda _: web.json_response({"status": "ok"}))
    app["bot_settings"] = settings
    app["adapter"] = adapter

    return app


# =============================================================================
# Genie Bot Handler
# =============================================================================

class GenieBot(TeamsActivityHandler):
    """
    Bot that handles Teams messages and routes them to Databricks Genie API.
    Performs OBO token exchange to preserve user identity for RLS.
    Uses TeamsActivityHandler for proper Teams SSO support.
    """

    def __init__(
        self,
        bot_settings: BotSettings | None = None,
        genie_settings: Settings | None = None,
    ):
        super().__init__()
        self._bot_settings = bot_settings or BotSettings()
        self._genie_settings = genie_settings or Settings()
        self._token_cache = TokenCache()

        # State management
        storage = MemoryStorage()
        self._conversation_state = ConversationState(storage)
        self._user_state = UserState(storage)
        self._dialog_state_accessor = self._conversation_state.create_property("DialogState")
        self._user_conversations_accessor = self._user_state.create_property("GenieConversations")
        # Store last query result for chart generation
        self._user_query_data_accessor = self._user_state.create_property("LastQueryData")
        # Store pending question during authentication
        self._pending_question_accessor = self._user_state.create_property("PendingQuestion")
        # Store current selected space ID
        self._current_space_accessor = self._user_state.create_property("CurrentSpaceId")

        # Dialogs
        self._dialogs = DialogSet(self._dialog_state_accessor)
        self._dialogs.add(TeamsSsoDialog(self._bot_settings, self._genie_settings))

        # Genie clients cache (mapped by space_id)
        self._genie_clients: dict[str, GenieClient] = {}

    async def on_turn(self, turn_context: TurnContext) -> None:
        await super().on_turn(turn_context)
        await self._conversation_state.save_changes(turn_context)
        await self._user_state.save_changes(turn_context)

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        try:
            # First, check if there's an active dialog that needs to continue (e.g., OAuth code entry)
            dialog_context = await self._dialogs.create_context(turn_context)
            results = await dialog_context.continue_dialog()

            # If dialog completed with a token result, process any pending question
            if results.status == DialogTurnStatus.Complete:
                if results.result and hasattr(results.result, 'success') and results.result.success:
                    # Dialog completed successfully with token
                    # Check if there's a pending question to process
                    user_id = turn_context.activity.from_property.id
                    pending_questions = await self._pending_question_accessor.get(turn_context, dict)
                    pending_question = pending_questions.get(user_id)

                    if pending_question:
                        # Clear the pending question
                        del pending_questions[user_id]
                        # Process the pending question now that we have a token
                        await self._process_genie_query(turn_context, pending_question)
                return

            # If dialog is waiting for input (e.g., OAuth code), don't process as new message
            if results.status == DialogTurnStatus.Waiting:
                return

            # No active dialog, process as normal message
            user_message = turn_context.activity.text
            activity_value = turn_context.activity.value  # Adaptive Card submit data

            # Check if this is an Adaptive Card button click (Web Chat sends as message with value)
            if activity_value and isinstance(activity_value, dict):
                action_type = activity_value.get("action")

                if action_type == "show_chart":
                    chart_type = activity_value.get("chart_type", "bar")
                    await self._handle_show_chart(turn_context, chart_type)
                    return
                elif action_type == "download_csv":
                    await self._handle_download_csv(turn_context)
                    return
                elif action_type == "download_png":
                    chart_type = activity_value.get("chart_type", "bar")
                    await self._handle_download_png(turn_context, chart_type)
                    return
                elif action_type == "ask_question":
                    # Handle suggested question click
                    question = activity_value.get("question", "")
                    if question:
                        await self._process_genie_query(turn_context, question)
                    return
                elif action_type == "select_space":
                    space_id = activity_value.get("space_id")
                    if space_id:
                        await self._handle_select_space(turn_context, space_id)
                    return

            if not user_message:
                await turn_context.send_activity("Please send a text message.")
                return

            lower_message = user_message.lower().strip()

            if lower_message in ("signout", "sign out", "logout", "log out"):
                await self._handle_signout(turn_context)
            elif lower_message in ("new", "new conversation", "reset"):
                await self._handle_new_conversation(turn_context)
            elif lower_message in ("history", "conversations", "list"):
                await self._handle_list_conversations(turn_context)
            elif lower_message in ("switch space", "change space", "spaces"):
                await self._handle_switch_space(turn_context)
            else:
                await self._process_genie_query(turn_context, user_message)
        except Exception:
            raise

    def _get_genie_client_for_space(self, space_id: str) -> GenieClient:
        """Get or create a Genie client for a specific space."""
        if space_id not in self._genie_clients:
            self._genie_clients[space_id] = GenieClient(
                str(self._genie_settings.databricks_host),
                space_id
            )
        return self._genie_clients[space_id]

    async def _get_target_space_id(self, turn_context: TurnContext) -> str | None:
        """
        Determine which space to use for the current turn.
        
        Returns:
            Space ID string if determined, or None if user needs to select one.
        """
        # 1. If only one space configured, return it
        if len(self._genie_settings.genie_spaces) == 1:
            return list(self._genie_settings.genie_spaces.values())[0]

        # 2. Check user's selected space
        current_space_id = await self._current_space_accessor.get(turn_context)
        
        # 3. Validate that the stored space ID still exists in config
        all_ids = self._genie_settings.genie_spaces.values()
        if current_space_id and current_space_id in all_ids:
            return current_space_id
            
        return None

    async def _prompt_for_space(self, turn_context: TurnContext) -> None:
        """Send an Adaptive Card to select a space."""
        actions = []
        for name, space_id in self._genie_settings.genie_spaces.items():
            actions.append({
                "type": "Action.Submit",
                "title": name,
                "data": {
                    "action": "select_space",
                    "space_id": space_id
                }
            })

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Please select a Genie Space:",
                    "size": "Medium",
                    "weight": "Bolder"
                }
            ],
            "actions": actions
        }

        attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card
        )
        await turn_context.send_activity(Activity(
            type=ActivityTypes.message,
            attachments=[attachment]
        ))

    async def _handle_switch_space(self, turn_context: TurnContext) -> None:
        """Handle 'switch space' command."""
        await self._current_space_accessor.delete(turn_context)
        await self._prompt_for_space(turn_context)

    async def _handle_select_space(self, turn_context: TurnContext, space_id: str) -> None:
        """Handle space selection action."""
        # Validate space ID
        space_name = next(
            (name for name, sid in self._genie_settings.genie_spaces.items() if sid == space_id),
            None
        )
        
        if not space_name:
            await turn_context.send_activity("Invalid space selected.")
            return

        await self._current_space_accessor.set(turn_context, space_id)
        
        # Also reset conversation when switching spaces
        user_conversations = await self._user_conversations_accessor.get(turn_context, dict)
        user_id = turn_context.activity.from_property.id
        if user_id in user_conversations:
            del user_conversations[user_id]
            
        await turn_context.send_activity(f"Switched to **{space_name}**. Ask me a question!")

    async def on_teams_signin_verify_state(self, turn_context: TurnContext) -> None:
        """Handle Teams SSO token exchange verification."""
        # Continue any active dialog to process the sign-in verification
        dialog_context = await self._dialogs.create_context(turn_context)
        await dialog_context.continue_dialog()

    async def on_invoke_activity(self, turn_context: TurnContext) -> InvokeResponse:
        """Handle Adaptive Card action invokes (button clicks)."""
        activity = turn_context.activity

        # Handle Adaptive Card Action.Submit
        if activity.name == "adaptiveCard/action":
            action_data = activity.value.get("action", {}).get("data", {})
            action_type = action_data.get("action")

            if action_type == "show_chart":
                chart_type = action_data.get("chart_type", "bar")
                await self._handle_show_chart(turn_context, chart_type)
                return InvokeResponse(status=200)

            elif action_type == "download_csv":
                await self._handle_download_csv(turn_context)
                return InvokeResponse(status=200)

            elif action_type == "download_png":
                chart_type = action_data.get("chart_type", "bar")
                await self._handle_download_png(turn_context, chart_type)
                return InvokeResponse(status=200)

                if question:
                    await self._process_genie_query(turn_context, question)
                return InvokeResponse(status=200)

            elif action_type == "select_space":
                space_id = action_data.get("space_id")
                if space_id:
                    await self._handle_select_space(turn_context, space_id)
                return InvokeResponse(status=200)

        # Fallback to parent handler
        return await super().on_invoke_activity(turn_context)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Hello! I'm the Genie Bot. Ask me questions about your data.\n\n"
                    "Commands:\n"
                    "- Type your question to query Genie\n"
                    "- Type 'new' to start a new conversation\n"
                    "- Type 'history' to see recent conversations\n"
                    "- Type 'signout' to sign out"
                )

    async def _handle_signout(self, turn_context: TurnContext) -> None:
        success = await sign_out_user(turn_context, self._bot_settings.oauth_connection_name)
        msg = "You have been signed out." if success else "Sign out failed. Please try again."
        await turn_context.send_activity(msg)

    async def _handle_new_conversation(self, turn_context: TurnContext) -> None:
        user_conversations = await self._user_conversations_accessor.get(turn_context, dict)
        user_id = turn_context.activity.from_property.id
        if user_id in user_conversations:
            del user_conversations[user_id]
            await turn_context.send_activity("Conversation reset. Next question starts fresh.")
        else:
            await turn_context.send_activity("No active conversation to reset.")

    async def _find_recent_conversation(self, client: GenieClient, databricks_token: str) -> str | None:
        """
        Find user's most recent conversation from Databricks.

        This enables conversation resumption after logout/login or app restart.
        Conversations are stored in Databricks, so we just need to query for them.

        Args:
        Args:
            client: The GenieClient for the specific space
            databricks_token: The user's Databricks access token

        Returns:
            The most recent conversation_id, or None if no conversations exist
        """
        try:
            conversation_id = await asyncio.to_thread(
                client.get_most_recent_conversation,
                databricks_token,
            )
            return conversation_id
        except Exception:
            # If we can't retrieve conversations, just start fresh
            return None

    async def _get_databricks_token_silently(
        self, turn_context: TurnContext
    ) -> tuple[str | None, str | None]:
        """
        Get Databricks token silently, handling SSO and token exchange.

        This method tries to get a valid Databricks token without user interaction:
        1. Get SSO token from Bot Framework cache
        2. Exchange for Databricks token (with caching and retry)

        Args:
            turn_context: The current turn context

        Returns:
            Tuple of (databricks_token, error_message)
            - On success: (token_string, None)
            - On silent failure (needs auth): (None, None)
            - On hard failure: (None, error_string)
        """
        # Step 1: Try to get SSO token silently
        sso_result = await get_token_from_context(
            turn_context, self._bot_settings.oauth_connection_name
        )

        if not sso_result.success or not sso_result.token:
            # Silent SSO failed - user needs to authenticate interactively
            return None, None

        # Step 2: Exchange for Databricks token (cached, with retry)
        try:
            databricks_token = await exchange_aad_for_databricks_token_async(
                self._genie_settings,
                sso_result.token,
                self._token_cache,
            )
            return databricks_token.access_token, None
        except TokenExchangeError as e:
            error_msg = str(e)
            # Check if this is a token expiry issue that might be resolved by re-auth
            if "invalid token" in error_msg.lower() or "401" in error_msg:
                # SSO token might be stale, need re-auth
                return None, None
            # Other errors (network, circuit breaker, etc.) - return as error
            return None, f"Token exchange failed: {e}"

    async def _handle_list_conversations(self, turn_context: TurnContext) -> None:
        """List recent conversations for the user."""
        # Get Databricks token first
        sso_result = await get_token_from_context(
            turn_context, self._bot_settings.oauth_connection_name
        )
        if not sso_result.success or not sso_result.token:
            await turn_context.send_activity("Please sign in first to view conversations.")
            return

        try:
            databricks_token = await exchange_aad_for_databricks_token_async(
                self._genie_settings,
                sso_result.token,
                self._token_cache,
            )
        except TokenExchangeError as e:
            await turn_context.send_activity(f"Token exchange failed: {e}")
            return

        space_id = await self._get_target_space_id(turn_context)
        if not space_id:
            await self._prompt_for_space(turn_context)
            return

        # Get conversations from Databricks
        try:
            client = self._get_genie_client_for_space(space_id)
            result = await asyncio.to_thread(
                client.list_conversations,
                databricks_token.access_token,
                page_size=5,
            )
            conversations = result.get("conversations", [])

            if not conversations:
                await turn_context.send_activity("You have no previous conversations.")
                return

            # Format conversations list
            lines = ["**Your Recent Conversations:**\n"]
            for i, conv in enumerate(conversations, 1):
                title = conv.get("title", "Untitled")
                conv_id = conv.get("conversation_id", "")[:8]  # Show first 8 chars
                lines.append(f"{i}. {title} (ID: {conv_id}...)")

            await turn_context.send_activity("\n".join(lines))

        except Exception as e:
            await turn_context.send_activity(f"Could not retrieve conversations: {e}")

    async def _handle_show_chart(self, turn_context: TurnContext, chart_type_str: str) -> None:
        """Generate and send a chart based on stored query data."""
        # Get stored query data
        user_query_data = await self._user_query_data_accessor.get(turn_context, dict)
        user_id = turn_context.activity.from_property.id

        stored_data = user_query_data.get(user_id)
        if not stored_data:
            await turn_context.send_activity("No data available for charting. Please run a query first.")
            return

        columns = stored_data.get("columns", [])
        rows = stored_data.get("rows", [])

        if not columns or not rows:
            await turn_context.send_activity("No data available for charting.")
            return

        # Convert string to ChartType
        try:
            chart_type = ChartType(chart_type_str)
        except ValueError:
            chart_type = ChartType.BAR

        # Generate chart
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        chart_result = await asyncio.to_thread(
            generate_chart,
            columns,
            rows,
            chart_type,
            "Query Results"
        )

        if chart_result.success and chart_result.image_base64:
            # Send chart as image attachment
            await self._send_chart_image(
                turn_context,
                chart_result.image_base64,
                chart_type,
                columns,
                rows
            )
        else:
            await turn_context.send_activity(
                f"Could not generate {chart_type.value} chart: {chart_result.error}"
            )

    async def _handle_download_csv(self, turn_context: TurnContext) -> None:
        """Send CSV download of query data."""
        user_query_data = await self._user_query_data_accessor.get(turn_context, dict)
        user_id = turn_context.activity.from_property.id

        stored_data = user_query_data.get(user_id)
        if not stored_data:
            await turn_context.send_activity("No data available for download.")
            return

        columns = stored_data.get("columns", [])
        rows = stored_data.get("rows", [])

        csv_content = await asyncio.to_thread(export_to_csv, columns, rows)
        csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')

        # Send as file attachment
        attachment = Attachment(
            content_type="text/csv",
            content_url=f"data:text/csv;base64,{csv_base64}",
            name="query_results.csv"
        )

        reply = Activity(
            type=ActivityTypes.message,
            text="Here's your data as CSV:",
            attachments=[attachment]
        )
        await turn_context.send_activity(reply)

    async def _handle_download_png(self, turn_context: TurnContext, chart_type_str: str) -> None:
        """Send PNG download of chart."""
        user_query_data = await self._user_query_data_accessor.get(turn_context, dict)
        user_id = turn_context.activity.from_property.id

        stored_data = user_query_data.get(user_id)
        if not stored_data:
            await turn_context.send_activity("No data available for chart download.")
            return

        columns = stored_data.get("columns", [])
        rows = stored_data.get("rows", [])

        try:
            chart_type = ChartType(chart_type_str)
        except ValueError:
            chart_type = ChartType.BAR

        chart_result = await asyncio.to_thread(
            generate_chart,
            columns,
            rows,
            chart_type,
            "Query Results"
        )

        if chart_result.success and chart_result.image_base64:
            attachment = Attachment(
                content_type="image/png",
                content_url=f"data:image/png;base64,{chart_result.image_base64}",
                name=f"chart_{chart_type.value}.png"
            )

            reply = Activity(
                type=ActivityTypes.message,
                text=f"Here's your {chart_type.value} chart:",
                attachments=[attachment]
            )
            await turn_context.send_activity(reply)
        else:
            await turn_context.send_activity(f"Could not generate chart: {chart_result.error}")

    async def _send_chart_image(
        self,
        turn_context: TurnContext,
        image_base64: str,
        current_chart_type: ChartType,
        columns: list[str],
        rows: list[list[Any]]
    ) -> None:
        """Send chart image with type selection buttons."""
        # Create image attachment
        image_attachment = Attachment(
            content_type="image/png",
            content_url=f"data:image/png;base64,{image_base64}",
            name=f"chart_{current_chart_type.value}.png"
        )

        # Send image
        image_activity = Activity(
            type=ActivityTypes.message,
            attachments=[image_attachment]
        )
        await turn_context.send_activity(image_activity)

        # Send Adaptive Card with chart type options
        card = self._create_chart_options_card(current_chart_type)
        card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card
        )

        card_activity = Activity(
            type=ActivityTypes.message,
            attachments=[card_attachment]
        )
        await turn_context.send_activity(card_activity)

    def _create_chart_options_card(self, current_type: ChartType) -> dict:
        """Create Adaptive Card for chart type selection."""
        chart_options = get_chart_type_options()

        # Create action buttons for each chart type
        actions = []
        for opt in chart_options:
            is_current = opt["value"] == current_type.value
            actions.append({
                "type": "Action.Submit",
                "title": f"{'✓ ' if is_current else ''}{opt['title']}",
                "data": {
                    "action": "show_chart",
                    "chart_type": opt["value"]
                }
            })

        # Add download buttons
        actions.append({
            "type": "Action.Submit",
            "title": "⬇️ Download PNG",
            "data": {
                "action": "download_png",
                "chart_type": current_type.value
            }
        })
        actions.append({
            "type": "Action.Submit",
            "title": "📄 Download CSV",
            "data": {
                "action": "download_csv"
            }
        })

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Change chart type or download:",
                    "size": "Small",
                    "weight": "Lighter"
                }
            ],
            "actions": actions
        }

    def _create_show_chart_card(self, chart_data: ChartData) -> dict:
        """Create Adaptive Card with 'Show Chart' button."""
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📊 Chart available ({chart_data.reason})",
                    "size": "Small",
                    "wrap": True
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": f"📊 Show {chart_data.recommended_type.value.title()} Chart",
                    "data": {
                        "action": "show_chart",
                        "chart_type": chart_data.recommended_type.value
                    }
                },
                {
                    "type": "Action.Submit",
                    "title": "📄 Download CSV",
                    "data": {
                        "action": "download_csv"
                    }
                }
            ]
        }

    def _extract_suggested_questions(self, genie_result: dict) -> list[str]:
        """
        Extract suggested follow-up questions from Genie response.

        Genie returns suggested questions in the attachments array when available.

        Args:
            genie_result: The raw Genie API response

        Returns:
            List of suggested question strings, or empty list
        """
        suggestions = []
        attachments = genie_result.get("attachments", [])

        for att in attachments:
            if "suggested_questions" in att:
                suggested = att.get("suggested_questions", [])
                if isinstance(suggested, list):
                    for q in suggested:
                        if isinstance(q, str):
                            suggestions.append(q)
                        elif isinstance(q, dict):
                            # Handle if questions are objects with 'question' field
                            text = q.get("question") or q.get("text") or q.get("content")
                            if text:
                                suggestions.append(text)

        return suggestions[:5]  # Limit to 5 suggestions

    def _create_suggested_questions_card(self, questions: list[str]) -> dict:
        """
        Create an Adaptive Card with suggested follow-up questions as clickable buttons.

        Args:
            questions: List of suggested questions

        Returns:
            Adaptive Card dict
        """
        actions = []
        for question in questions:
            # Truncate long questions for button display
            display_text = question if len(question) <= 50 else question[:47] + "..."
            actions.append({
                "type": "Action.Submit",
                "title": display_text,
                "data": {
                    "action": "ask_question",
                    "question": question
                }
            })

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "💡 You might also want to ask:",
                    "size": "Small",
                    "weight": "Lighter",
                    "wrap": True
                }
            ],
            "actions": actions
        }

    async def _process_genie_query(self, turn_context: TurnContext, question: str) -> None:
        # Resolve target space first
        space_id = await self._get_target_space_id(turn_context)
        if not space_id:
            await self._prompt_for_space(turn_context)
            return
            
        # Send typing indicator using Activity object (not dict)
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        # Try to get Databricks token silently (seamless refresh)
        databricks_token_str, error = await self._get_databricks_token_silently(turn_context)

        if error:
            # Hard failure (network, circuit breaker, etc.)
            await turn_context.send_activity(error)
            return

        if not databricks_token_str:
            # Silent auth failed - need interactive sign-in
            # Store the question so we can process it after auth completes
            user_id = turn_context.activity.from_property.id
            pending_questions = await self._pending_question_accessor.get(turn_context, dict)
            pending_questions[user_id] = question

            # Start the OAuth dialog
            dialog_context = await self._dialogs.create_context(turn_context)
            result = await dialog_context.begin_dialog(TeamsSsoDialog.__name__)
            if result.status == DialogTurnStatus.Complete and result.result:
                # Auth completed immediately (rare) - continue with the query
                if result.result.success:
                    # Clear pending question
                    pending_questions.pop(user_id, None)
                    # Try to get token again
                    databricks_token_str, error = await self._get_databricks_token_silently(turn_context)
                    if error:
                        await turn_context.send_activity(error)
                        return
                    if not databricks_token_str:
                        await turn_context.send_activity("Authentication failed. Please try again.")
                        return
                else:
                    await turn_context.send_activity(f"Authentication failed: {result.result.error}")
                    return
            else:
                # Waiting for OAuth - question will be processed after auth completes
                return

        # Create a token result object for the rest of the method
        class TokenHolder:
            access_token: str
        databricks_token = TokenHolder()
        databricks_token.access_token = databricks_token_str

        # Call Genie API
        user_id = turn_context.activity.from_property.id
        user_conversations = await self._user_conversations_accessor.get(turn_context, dict)
        genie_conversation_id = user_conversations.get(user_id)

        # If no local conversation ID, try to resume from Databricks
        # This handles logout/login and app restart scenarios
        if not genie_conversation_id:
            client = self._get_genie_client_for_space(space_id)
            resumed_id = await self._find_recent_conversation(client, databricks_token.access_token)
            if resumed_id:
                genie_conversation_id = resumed_id
                user_conversations[user_id] = resumed_id
                # Silently resumed - user doesn't need to know

        # Get client for the target space
        client = self._get_genie_client_for_space(space_id)

        try:
            if genie_conversation_id:
                result = await asyncio.to_thread(
                    client.send_message,
                    databricks_token.access_token,
                    genie_conversation_id,
                    question,
                )
            else:
                result = await asyncio.to_thread(
                    client.start_conversation,
                    databricks_token.access_token,
                    question,
                )
                new_id = result.get("conversation_id") or result.get("id")
                if new_id:
                    user_conversations[user_id] = new_id
        except Exception as e:
            await turn_context.send_activity(f"Genie API error: {e}")
            return

        # Extract response and chart data
        response_data = await asyncio.to_thread(
            self._extract_response_with_chart_data,
            result,
            databricks_token.access_token,
            client,
        )

        response_text = response_data.get("text", "")
        chart_data = response_data.get("chart_data")
        columns = response_data.get("columns", [])
        rows = response_data.get("rows", [])
        suggested_questions = response_data.get("suggested_questions", [])

        # Send the text response
        if response_text:
            await turn_context.send_activity(response_text)

        # If chartable data exists, store it and send chart card
        if chart_data and chart_data.chartable and columns and rows:
            # Store data for chart generation
            user_query_data = await self._user_query_data_accessor.get(turn_context, dict)
            user_id = turn_context.activity.from_property.id
            user_query_data[user_id] = {
                "columns": columns,
                "rows": rows
            }

            # Send "Show Chart" button
            card = self._create_show_chart_card(chart_data)
            card_attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=card
            )
            card_activity = Activity(
                type=ActivityTypes.message,
                attachments=[card_attachment]
            )
            await turn_context.send_activity(card_activity)

        # Send suggested questions as clickable buttons
        if suggested_questions:
            suggestions_card = self._create_suggested_questions_card(suggested_questions)
            suggestions_attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=suggestions_card
            )
            suggestions_activity = Activity(
                type=ActivityTypes.message,
                attachments=[suggestions_attachment]
            )
            await turn_context.send_activity(suggestions_activity)

    def _extract_response_with_chart_data(
        self,
        genie_result: dict,
        user_token: str | None = None,
        client: GenieClient | None = None,
    ) -> dict[str, Any]:
        """
        Extract response text and chart-compatible data from Genie API response.

        Returns:
            dict with keys:
            - text: str - formatted response text
            - columns: list[str] - column names (if query result)
            - rows: list[list] - data rows (if query result)
            - chart_data: ChartData | None - chart analysis result
            - suggested_questions: list[str] - follow-up suggestions
        """
        text = self._extract_response(genie_result, user_token, client)
        columns = []
        rows = []
        chart_data = None

        # Try to extract data for charting from attachments
        attachments = genie_result.get("attachments", [])
        for att in attachments:
            if "query_result" in att:
                cols, rws = self._extract_columns_rows(att)
                if cols and rws:
                    columns = cols
                    rows = rws
                    break
            elif "query" in att and user_token and client:
                # Fetch query result if not included
                conversation_id = genie_result.get("conversation_id", "")
                message_id = genie_result.get("id", "") or genie_result.get("message_id", "")
                att_id = att.get("attachment_id")

                if conversation_id and message_id and att_id:
                    try:
                        query_result = client.get_query_result(
                            user_token, conversation_id, message_id, att_id
                        )
                        if query_result and "error" not in query_result:
                            cols, rws = self._extract_columns_rows({"query_result": query_result})
                            if cols and rws:
                                columns = cols
                                rows = rws
                                break
                    except Exception:
                        pass  # Continue without chart data

        # Analyze data for chart compatibility
        if columns and rows:
            chart_data = analyze_data_for_chart(columns, rows)

        # Extract suggested follow-up questions
        suggested_questions = self._extract_suggested_questions(genie_result)

        return {
            "text": text,
            "columns": columns,
            "rows": rows,
            "chart_data": chart_data,
            "suggested_questions": suggested_questions,
        }

    def _extract_columns_rows(self, attachment: dict) -> tuple[list[str], list[list[Any]]]:
        """Extract columns and rows from a query result attachment."""
        data = attachment.get("query_result", {}) or attachment.get("data", {}) or attachment

        columns = []
        rows = []

        if isinstance(data, dict):
            # Format 1: Direct columns/rows
            columns = data.get("columns", [])
            rows = data.get("rows", [])

            # Format 2: Statement result format with 'statement_response'
            if not columns and "statement_response" in data:
                stmt_resp = data.get("statement_response", {})
                result = stmt_resp.get("result", {})
                if result:
                    manifest = stmt_resp.get("manifest", {})
                    schema = manifest.get("schema", {})
                    schema_cols = schema.get("columns", [])
                    if schema_cols:
                        columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]
                    rows = result.get("data_array", [])

            # Format 3: Columns in 'schema'
            if not columns and "schema" in data:
                schema = data.get("schema", {})
                schema_cols = schema.get("columns", [])
                if schema_cols:
                    columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]

            # Format 4: Rows in 'data_array'
            if not rows:
                rows = data.get("data_array", [])

            # Format 5: Direct result from get_query_result API
            if not columns and "manifest" in data:
                manifest = data.get("manifest", {})
                schema = manifest.get("schema", {})
                schema_cols = schema.get("columns", [])
                if schema_cols:
                    columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]
                result = data.get("result", {})
                rows = result.get("data_array", [])

        return columns, rows

    def _extract_response(
        self,
        genie_result: dict,
        user_token: str | None = None,
        client: GenieClient | None = None,
    ) -> str:
        """Extract human-readable content from Genie API response."""
        status = genie_result.get("status", "")
        conversation_id = genie_result.get("conversation_id", "")
        message_id = genie_result.get("id", "") or genie_result.get("message_id", "")

        # Handle error/timeout statuses
        if status == "TIMEOUT":
            return "Sorry, the query took too long to process. Please try again."
        if status in ("FAILED", "CANCELLED", "ERROR"):
            error_msg = genie_result.get("error", "Unknown error")
            return f"Query failed: {error_msg}"

        # Try to extract from 'attachments' array (completed message format)
        attachments = genie_result.get("attachments", [])
        if attachments:
            results = []
            has_query_result = False

            # First pass: check what we have
            for att in attachments:
                if "query_result" in att:
                    has_query_result = True

            # Second pass: process attachments
            for att in attachments:
                # Check for 'text' attachment (natural language response)
                if "text" in att:
                    text_content = att.get("text", {})
                    if isinstance(text_content, dict):
                        content = text_content.get("content", "")
                        if content:
                            results.append(content)
                    elif isinstance(text_content, str):
                        results.append(text_content)

                # Check for 'query' attachment (generated SQL)
                elif "query" in att:
                    query_content = att.get("query", {})
                    if isinstance(query_content, dict):
                        sql = query_content.get("query", "")
                        description = query_content.get("description", "")
                        if description:
                            results.append(f"**Analysis:** {description}")
                        if sql:
                            results.append(f"```sql\n{sql}\n```")

                        # If no query_result attachment exists, try to fetch the results
                        if not has_query_result and user_token and client and conversation_id and message_id:
                            att_id = att.get("attachment_id")
                            if att_id:
                                try:
                                    query_result = client.get_query_result(
                                        user_token, conversation_id, message_id, att_id
                                    )
                                    if query_result and "error" not in query_result:
                                        # Wrap it in the expected format
                                        results.append(self._format_query_result({"query_result": query_result}))
                                except Exception:
                                    pass  # Continue without fetched results

                # Check for 'query_result' attachment (data results)
                elif "query_result" in att:
                    results.append(self._format_query_result(att))

                # Check for 'suggested_questions' (skip these)
                elif "suggested_questions" in att:
                    pass  # Skip suggested questions

            if results:
                return "\n\n".join(results)

        # Try 'message' field (older format)
        message = genie_result.get("message", {})
        if isinstance(message, dict):
            content = message.get("content")
            if content:
                return content

            msg_attachments = message.get("attachments", [])
            for att in msg_attachments:
                if "query_result" in att:
                    return self._format_query_result(att)

        # Try direct 'content' field - but only if not COMPLETED (meaning still processing)
        content = genie_result.get("content")
        if content and isinstance(content, str) and status != "COMPLETED":
            return f"Query submitted: {content}"

        # Fallback - return status info
        if status:
            return f"Query status: {status}"

        return f"Response received: {genie_result}"

    def _format_query_result(self, attachment: dict) -> str:
        """Format query result as markdown table."""
        # Try different data locations - the API can return data in various formats
        data = attachment.get("query_result", {}) or attachment.get("data", {}) or attachment

        columns = []
        rows = []

        # Handle nested structure
        if isinstance(data, dict):
            # Format 1: Direct columns/rows
            columns = data.get("columns", [])
            rows = data.get("rows", [])

            # Format 2: Statement result format with 'statement_response'
            if not columns and "statement_response" in data:
                stmt_resp = data.get("statement_response", {})
                result = stmt_resp.get("result", {})
                if result:
                    # Columns from manifest.schema.columns
                    manifest = stmt_resp.get("manifest", {})
                    schema = manifest.get("schema", {})
                    schema_cols = schema.get("columns", [])
                    if schema_cols:
                        columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]
                    # Rows from result.data_array
                    rows = result.get("data_array", [])

            # Format 3: Columns in 'schema'
            if not columns and "schema" in data:
                schema = data.get("schema", {})
                schema_cols = schema.get("columns", [])
                if schema_cols:
                    columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]

            # Format 4: Rows in 'data_array'
            if not rows:
                rows = data.get("data_array", [])

            # Format 5: Direct result from get_query_result API
            if not columns and "columns" not in data and "manifest" in data:
                manifest = data.get("manifest", {})
                schema = manifest.get("schema", {})
                schema_cols = schema.get("columns", [])
                if schema_cols:
                    columns = [col.get("name", f"col_{i}") for i, col in enumerate(schema_cols)]
                result = data.get("result", {})
                rows = result.get("data_array", [])

        if not columns or not rows:
            # Check if there's a row_count indicating empty results
            row_count = data.get("row_count", -1) if isinstance(data, dict) else -1
            if row_count == 0:
                return "Query returned no results."
            return "Query returned no data."

        # Build markdown table
        header = "| " + " | ".join(str(c) for c in columns) + " |"
        sep = "| " + " | ".join(["---"] * len(columns)) + " |"

        # Limit rows and truncate long values
        display_rows = rows[:50]
        body_lines = []
        for row in display_rows:
            formatted_values = []
            for v in row:
                str_val = str(v) if v is not None else ""
                # Truncate long values
                if len(str_val) > 50:
                    str_val = str_val[:47] + "..."
                # Escape pipe characters
                str_val = str_val.replace("|", "\\|")
                formatted_values.append(str_val)
            body_lines.append("| " + " | ".join(formatted_values) + " |")

        body = "\n".join(body_lines)
        result = f"{header}\n{sep}\n{body}"

        if len(rows) > 50:
            result += f"\n\n*Showing 50 of {len(rows)} rows*"

        return result

    def _format_table(self, attachment: dict) -> str:
        """Alias for backward compatibility."""
        return self._format_query_result(attachment)
