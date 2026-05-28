
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from botbuilder.core import TurnContext, MemoryStorage, UserState, ConversationState
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount, ConversationAccount
from genie_api_obo_rls.bot import GenieBot
from genie_api_obo_rls.config import Settings, BotSettings

# Mock adapter (minimal needed for TurnContext)
class MockAdapter:
    async def send_activities(self, context, activities):
        for activity in activities:
            print(f"BOT SAYS: {activity.text}")
        return []
    
    async def delete_activity(self, context, reference):
        pass

async def main():
    print("--- Starting Local Reproduction Test ---")
    
    # Setup mocks
    bot_settings = BotSettings(
        microsoft_app_id="mock_id",
        microsoft_app_password="mock_password"
    )
    # Mock settings with spaces
    genie_settings = Settings(
        databricks_host="https://mock.databricks.com",
        genie_space_id="default_space",
        account_id="mock_account",
        genie_spaces={"Primary": "space_1", "Secondary": "space_2"}
    )
    
    bot = GenieBot(bot_settings, genie_settings)
    adapter = MockAdapter()
    
    # 1. Create a "Select Space" Activity
    # This mimics exactly what Adaptive Card Action.Submit sends in Web Chat
    # text is None (or empty), value is the data dict
    activity = Activity(
        type=ActivityTypes.message,
        text=None,
        value={"action": "select_space", "space_id": "space_2"},
        channel_id="emulator",
        from_property=ChannelAccount(id="user1", name="User 1"),
        conversation=ConversationAccount(id="convo1"),
        recipient=ChannelAccount(id="bot", name="Bot"),
        service_url="http://localhost:8080"
    )
    
    context = TurnContext(adapter, activity)
    
    print("\n[TEST] Sending 'select_space' activity (Message with Value, No Text)...")
    try:
        await bot.on_turn(context)
        print("[TEST] on_turn completed.")
    except Exception as e:
        print(f"[TEST] Exception: {e}")

    # Check state manually
    # We need to peek into the storage to see if the state was saved, 
    # but since we mocked adapter we rely on print output "Switched to **Secondary**..."
    
    print("\n--- End Test ---")

if __name__ == "__main__":
    asyncio.run(main())
