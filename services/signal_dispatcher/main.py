"""
Signal Dispatcher Service - Main Entry Point

Routes trading signals to Telegram, WebSocket clients, and Trading Executor.
"""

import asyncio
import sys
from loguru import logger

from common.config import settings


async def main():
    """Main entry point for signal dispatcher service."""
    logger.info("Starting Signal Dispatcher Service...")
    logger.info(f"Telegram Enabled: {bool(settings.TELEGRAM_TOKEN)}")
    logger.info(f"Daily Report Time: {settings.DAILY_REPORT_TIME}")
    
    # TODO: Initialize Redis subscriber
    # TODO: Initialize Telegram bot
    # TODO: Initialize WebSocket broadcaster
    # TODO: Initialize signal formatter
    # TODO: Subscribe to signal:generated events
    
    logger.info("Signal Dispatcher Service started successfully")
    
    # Keep service running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down Signal Dispatcher Service...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
