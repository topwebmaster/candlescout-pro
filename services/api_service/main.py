"""
API Service - Main Entry Point

Provides REST and WebSocket interfaces for external access.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from common.config import settings

# Create FastAPI app
app = FastAPI(
    title="CandleScout Pro API",
    description="REST and WebSocket API for CandleScout Pro trading system",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting API Service...")
    logger.info(f"Host: {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"Workers: {settings.API_WORKERS}")
    logger.info(f"CORS Origins: {settings.cors_origins}")
    
    # TODO: Initialize database connection
    # TODO: Initialize Redis connection
    # TODO: Initialize WebSocket manager
    
    logger.info("API Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down API Service...")
    
    # TODO: Close database connection
    # TODO: Close Redis connection
    # TODO: Close WebSocket connections


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "CandleScout Pro API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "api-service",
        "version": "1.0.0"
    }


# TODO: Add REST endpoints
# @app.get("/api/v1/candles")
# @app.get("/api/v1/signals")
# @app.get("/api/v1/signals/{signal_id}")
# @app.get("/api/v1/analysis/latest")
# @app.get("/api/v1/stats")

# TODO: Add WebSocket endpoints
# @app.websocket("/ws/signals")
# @app.websocket("/ws/candles")
# @app.websocket("/ws/positions")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=settings.API_RELOAD,
        log_level=settings.API_LOG_LEVEL,
    )
