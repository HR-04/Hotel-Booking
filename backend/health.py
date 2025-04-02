from fastapi import APIRouter
from sqlalchemy import text
from rag import  vector_store, qa_chain
from data_gen import engine
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    health_status = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        health_status["database"] = "Connected"
    except Exception as e:
        health_status["database"] = f"Not Connected: {e}"
    
    health_status["vector_store"] = "initialized" if vector_store is not None else "not initialized"
    health_status["qa_chain"] = "initialized" if qa_chain is not None else "not initialized"
    
    overall_status = "200 OK" if all(status in ["Connected", "initialized"] for status in health_status.values()) else "In Active ❌"
    return {"status": "200 Ok ", "dependencies": health_status}
