"""Track mock LLM cost against a shared UTC daily budget."""
from datetime import date

from fastapi import HTTPException

from .config import settings
from .redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def check_budget(day: date) -> None:
    spent = float(r.get(f"agent:cost:{day.isoformat()}") or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(402, "Daily budget exhausted")


def record_cost(day: date, input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key = f"agent:cost:{day.isoformat()}"
    with r.pipeline() as transaction:
        transaction.incrbyfloat(key, cost)
        transaction.expire(key, 172800)
        transaction.execute()
    return cost
