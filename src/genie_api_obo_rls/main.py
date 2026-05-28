"""
Main entry point for Genie API OBO RLS service.

Usage:
    python -m genie_api_obo_rls.main --mode bot --port 8000   # Teams Bot
    python -m genie_api_obo_rls.main --mode api --port 8000   # Direct API
    python -m genie_api_obo_rls.main cli --question "Show sales"  # CLI query

Deploy to: Azure App Service (dbrx-webapp-genie-obo-rls)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import requests
from aiohttp import web


def _initialize_services() -> None:
    """Initialize Key Vault and Application Insights."""
    try:
        from .services import apply_keyvault_secrets_to_env
        count = apply_keyvault_secrets_to_env()
        if count > 0:
            print(f"Loaded {count} secrets from Key Vault")
    except Exception as e:
        print(f"Key Vault: {e}")

    try:
        from .services import get_telemetry_client
        if get_telemetry_client().is_configured:
            print("Application Insights enabled")
    except Exception as e:
        print(f"App Insights: {e}")


def run_bot_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the Bot Framework server for Teams integration."""
    _initialize_services()

    from .bot import GenieBot, create_bot_app
    from .config import BotSettings, Settings
    from .services import track_event

    print(f"Starting Genie Bot server on {host}:{port}")
    bot = GenieBot(bot_settings=BotSettings(), genie_settings=Settings())
    app = create_bot_app(bot, BotSettings())
    track_event("BotServerStarted", {"host": host, "port": str(port)})
    web.run_app(app, host=host, port=port)


def run_api_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI server for direct API access."""
    _initialize_services()

    import uvicorn
    from .api import app
    from .services import track_event

    print(f"Starting Genie API server on {host}:{port}")
    track_event("ApiServerStarted", {"host": host, "port": str(port)})
    uvicorn.run(app, host=host, port=port)


async def run_both_servers(host: str, bot_port: int, api_port: int) -> None:
    """Run both bot and API servers concurrently."""
    _initialize_services()

    import uvicorn
    from .api import app as fastapi_app
    from .bot import GenieBot, create_bot_app
    from .config import BotSettings, Settings

    print(f"Starting Bot on {host}:{bot_port}, API on {host}:{api_port}")

    bot = GenieBot(bot_settings=BotSettings(), genie_settings=Settings())
    bot_app = create_bot_app(bot, BotSettings())

    bot_runner = web.AppRunner(bot_app)
    await bot_runner.setup()
    await web.TCPSite(bot_runner, host, bot_port).start()

    config = uvicorn.Config(fastapi_app, host=host, port=api_port, log_level="info")
    try:
        await uvicorn.Server(config).serve()
    finally:
        await bot_runner.cleanup()


def cli_query(question: str, aad_token: str, service_url: str, conversation_id: str = "") -> int:
    """Query Genie via the running service."""
    if not aad_token:
        print("Missing AAD token. Set --aad-token or AAD_ACCESS_TOKEN.", file=sys.stderr)
        return 2

    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    response = requests.post(
        f"{service_url.rstrip('/')}/genie/ask",
        headers={"Authorization": f"Bearer {aad_token}"},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        print(f"Error: {response.status_code} {response.text}", file=sys.stderr)
        return 1

    print(json.dumps(response.json(), indent=2))
    return 0


def main() -> int:
    """Main entry point with server and CLI modes."""
    parser = argparse.ArgumentParser(description="Genie API OBO RLS Service")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Server command (default)
    server_parser = subparsers.add_parser("server", help="Run server")
    server_parser.add_argument("--mode", choices=["bot", "api", "both"], default="bot")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=8000)
    server_parser.add_argument("--bot-port", type=int, default=8000)
    server_parser.add_argument("--api-port", type=int, default=8001)

    # CLI command
    cli_parser = subparsers.add_parser("cli", help="Query via CLI")
    cli_parser.add_argument("--question", "-q", required=True, help="Question to ask")
    cli_parser.add_argument("--aad-token", default=os.getenv("AAD_ACCESS_TOKEN", ""))
    cli_parser.add_argument("--service-url", default=os.getenv("GENIE_SERVICE_URL", "http://127.0.0.1:8000"))
    cli_parser.add_argument("--conversation-id", default="")

    args = parser.parse_args()

    # Default to server mode if no command given
    if args.command is None or args.command == "server":
        mode = getattr(args, "mode", "bot")
        host = getattr(args, "host", "0.0.0.0")
        port = getattr(args, "port", 8000)

        try:
            if mode == "bot":
                run_bot_server(host, port)
            elif mode == "api":
                run_api_server(host, port)
            else:
                asyncio.run(run_both_servers(host, args.bot_port, args.api_port))
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "cli":
        return cli_query(args.question, args.aad_token, args.service_url, args.conversation_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
