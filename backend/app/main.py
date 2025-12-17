"""
FastAPI main application for the Reconciliation Agent.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Reconciliation Agent",
    description="AI-powered reconciliation logic discovery service",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Reconciliation Agent",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.config import settings

    # Check if API key is configured
    api_key_configured = bool(settings.OPENROUTER_API_KEY and len(settings.OPENROUTER_API_KEY) > 10)

    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "api_key_configured": api_key_configured,
        "model": settings.OPENROUTER_MODEL
    }

# Track route loading status
routes_loaded = False
routes_error = None

# Import and register routes directly (not in startup event)
try:
    from app.api.routes import router
    app.include_router(router)
    routes_loaded = True
    logger.info("API routes loaded successfully")
except Exception as e:
    routes_error = str(e)
    logger.error(f"Failed to load routes: {e}")
    import traceback
    traceback.print_exc()

@app.get("/debug")
async def debug_info():
    """Debug endpoint to check route loading status."""
    return {
        "routes_loaded": routes_loaded,
        "routes_error": routes_error,
        "registered_routes": [r.path for r in app.routes]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
