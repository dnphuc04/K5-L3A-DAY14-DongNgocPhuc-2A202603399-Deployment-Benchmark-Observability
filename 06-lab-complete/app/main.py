"""Production AI agent built on FastAPI and Redis."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from redis import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        })


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(settings.log_level)
logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    try:
        yield
    finally:
        r.close()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info("request", extra={"fields": {
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "ms": round((perf_counter() - start) * 1000, 2),
        }})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(503, "Redis is unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    day = datetime.now(timezone.utc).date()
    try:
        check_rate_limit(key)
        check_budget(day)
        answer = llm_ask(body.question)
        record_cost(day, len(body.question.split()) * 2, len(answer.split()) * 2)
    except RedisError:
        raise HTTPException(503, "Redis is unavailable") from None
    return {"question": body.question, "answer": answer}
