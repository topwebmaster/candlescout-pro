"""
Data Ingestion Service - Main Entry Point

Collects real-time market data from Binance and persists to TimescaleDB.
"""

import asyncio
import sys
from loguru import logger

from common.config import settings


async def main():
    """Main entry point for data ingestion service."""
    logger.info("Starting Data Ingestion Service...")
    logger.info(f"Symbol: {settings.BINANCE_SYMBOL}")
    logger.info(f"Interval: {settings.BINANCE_INTERVAL}")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    
    # TODO: Initialize WebSocket manager
    # TODO: Initialize REST fallback
    # TODO: Initialize tick aggregator
    # TODO: Initialize Redis cache
    # TODO: Start data collection
    
    logger.info("Data Ingestion Service started successfully")
    
    # Keep service running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down Data Ingestion Service...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
