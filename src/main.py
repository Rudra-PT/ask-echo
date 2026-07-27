import logging

from fastapi import FastAPI

from src.api.query import router as query_router
from src.api.upload import router as upload_router
from src.core.config import settings  

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Ask-Echo",
    version="0.1.0",
    description="Multi-format RAG backend powered by Gemini and Pinecone.",
)





app.include_router(upload_router)
app.include_router(query_router)







@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ask-echo"}
