import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from analytics import router as analytics_router
from rag import router as rag_router
from data_gen import router as data_gen_router
from health import router as health_router
from data_gen import start_notification_listener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(analytics_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(data_gen_router, prefix="/api")
app.include_router(health_router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        logger.info("Starting initialization sequence...")
        # 1. Initialize RAG components
        from rag import update_insights
        update_insights()
        
        # 2. Start database listener
        start_notification_listener()
        
        logger.info("✅ Backend services initialized successfully")
    except Exception as e:
        logger.error(f"🚨 Startup failed: {str(e)}")
        raise RuntimeError(f"Startup failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)