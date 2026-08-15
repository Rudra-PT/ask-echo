import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.query import router as query_router
from src.api.upload import router as upload_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ask-Echo",
    version="0.1.0",
    description="Multi-format RAG backend powered by Gemini and Pinecone.",
    redirect_slashes=False,  # prevents 307 redirects that break CORS
)

# ---------------------------------------------------------------------------
# CORS — must be added BEFORE any routers
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(upload_router)
app.include_router(query_router)

# ---------------------------------------------------------------------------
# Background scheduler — daily purge of vectors older than 7 days
# ---------------------------------------------------------------------------

_SEVEN_DAYS_SECS: int = 7 * 24 * 60 * 60


def purge_expired_vectors() -> None:
    """Delete Pinecone vectors whose `created_at` metadata is older than 7 days."""
    try:
        from src.services.vector import _get_index, INDEX_NAME  # local import avoids circular dep at startup

        cutoff_ts = time.time() - _SEVEN_DAYS_SECS
        index = _get_index()

        logger.info(
            "Running purge_expired_vectors: deleting vectors with created_at < %.0f (cutoff %s)",
            cutoff_ts,
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cutoff_ts)),
        )

        # Pinecone metadata filter: delete all records where created_at < cutoff
        index.delete(
            filter={"created_at": {"$lt": cutoff_ts}},
            namespace="public",
        )

        logger.info("purge_expired_vectors completed for index '%s'.", INDEX_NAME)
    except Exception as exc:
        # Never crash the scheduler — just log and continue
        logger.error("purge_expired_vectors failed: %s", exc)


scheduler = BackgroundScheduler()
scheduler.add_job(
    purge_expired_vectors,
    trigger="interval",
    days=1,
    id="purge_expired_vectors",
    replace_existing=True,
)
scheduler.start()
logger.info("APScheduler started — purge_expired_vectors runs every 24 h.")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ask-echo"}
