"""
Cost Controller for Jarvis
Tracks token usage, per-request cost, enforces daily/monthly budgets,
and can auto-downgrade models when budget is tight.
"""

import time
from datetime import datetime, date
from typing import Any, Dict, Optional, Tuple

import aiosqlite
from loguru import logger

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    logger.warning("tiktoken not installed – token counting will use estimates")


# Approximate cost per 1K tokens (input, output) in USD — kept up-to-date manually
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o":              (0.0025, 0.010),
    "gpt-4o-mini":         (0.00015, 0.0006),
    "gpt-4-turbo":         (0.01, 0.03),
    "gpt-4":               (0.03, 0.06),
    "gpt-3.5-turbo":       (0.0005, 0.0015),
    # Anthropic
    "claude-3-opus":       (0.015, 0.075),
    "claude-3-sonnet":     (0.003, 0.015),
    "claude-3-haiku":      (0.00025, 0.00125),
    "claude-3.5-sonnet":   (0.003, 0.015),
    # Google
    "gemini-pro":          (0.0005, 0.0015),
    "gemini-1.5-pro":      (0.00125, 0.005),
    "gemini-1.5-flash":    (0.000075, 0.0003),
    # Local — free
    "llama3.2":            (0.0, 0.0),
    "ollama/*":            (0.0, 0.0),
}


def _count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Count tokens using tiktoken when available, else estimate."""
    if tiktoken is not None:
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            pass
    # Rough estimate: 1 token ≈ 4 characters in English
    return max(1, len(text) // 4)


def _lookup_pricing(model: str) -> Tuple[float, float]:
    """Look up per-1K-token pricing for *model*. Falls back to gpt-4o-mini rates."""
    # Exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # Check prefix (e.g. "ollama/llama3.2" matches "ollama/*")
    for pattern, price in MODEL_PRICING.items():
        if pattern.endswith("/*") and model.startswith(pattern[:-2]):
            return price
    # Strip provider prefix ("openai/gpt-4o-mini" -> "gpt-4o-mini")
    base = model.split("/")[-1] if "/" in model else model
    if base in MODEL_PRICING:
        return MODEL_PRICING[base]
    logger.debug("No pricing entry for model={}, using gpt-4o-mini rates", model)
    return MODEL_PRICING["gpt-4o-mini"]


class CostController:
    """Tracks and limits API spending with SQLite persistence."""

    def __init__(self, db_path: str, daily_budget: float = 5.0, monthly_budget: float = 50.0) -> None:
        self.db_path = db_path
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self._session_cost: float = 0.0
        logger.info(
            "CostController initialized | daily={} monthly={}", daily_budget, monthly_budget
        )

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Create the cost_log table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cost_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    conversation_id TEXT,
                    prompt_preview TEXT
                )
                """
            )
            await db.commit()
        logger.debug("cost_log table ready")

    # ------------------------------------------------------------------
    # Budget queries
    # ------------------------------------------------------------------

    async def _total_cost_since(self, since_iso: str) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp >= ?",
                (since_iso,),
            )
            row = await cursor.fetchone()
            return float(row[0]) if row else 0.0

    async def get_daily_cost(self) -> float:
        """Total spend today (UTC)."""
        today = datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
        return await self._total_cost_since(today)

    async def get_monthly_cost(self) -> float:
        """Total spend this calendar month (UTC)."""
        first_of_month = datetime.utcnow().strftime("%Y-%m-01T00:00:00")
        return await self._total_cost_since(first_of_month)

    async def check_budget(self) -> Dict[str, Any]:
        """
        Return budget status and whether spending is allowed.

        Returns dict with keys: allowed, daily_remaining, monthly_remaining,
        daily_used, monthly_used, warning.
        """
        daily_used = await self.get_daily_cost()
        monthly_used = await self.get_monthly_cost()
        daily_remaining = self.daily_budget - daily_used
        monthly_remaining = self.monthly_budget - monthly_used

        allowed = daily_remaining > 0 and monthly_remaining > 0
        warning = ""
        if daily_remaining < self.daily_budget * 0.2:
            warning = "Daily budget almost exhausted"
        elif monthly_remaining < self.monthly_budget * 0.2:
            warning = "Monthly budget almost exhausted"

        return {
            "allowed": allowed,
            "daily_used": round(daily_used, 6),
            "monthly_used": round(monthly_used, 6),
            "daily_remaining": round(max(daily_remaining, 0), 6),
            "monthly_remaining": round(max(monthly_remaining, 0), 6),
            "warning": warning,
        }

    # ------------------------------------------------------------------
    # Model downgrade
    # ------------------------------------------------------------------

    async def maybe_downgrade_model(
        self, requested_model: str, cheap_model: str, local_model: str
    ) -> str:
        """
        If budget is tight, downgrade to a cheaper model automatically.
        Returns the model name to use.
        """
        budget = await self.check_budget()

        if not budget["allowed"]:
            logger.warning("Budget exhausted — forcing local model")
            return local_model

        # If less than 20% daily budget remains, use cheap model
        if budget["daily_remaining"] < self.daily_budget * 0.2:
            if requested_model != cheap_model and requested_model != local_model:
                logger.info(
                    "Budget tight — downgrading {} -> {}", requested_model, cheap_model
                )
                return cheap_model

        return requested_model

    # ------------------------------------------------------------------
    # Logging a request
    # ------------------------------------------------------------------

    def estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost in USD for a single request."""
        inp_rate, out_rate = _lookup_pricing(model)
        return (input_tokens / 1000.0) * inp_rate + (output_tokens / 1000.0) * out_rate

    async def log_usage(
        self,
        model: str,
        input_text: str,
        output_text: str,
        conversation_id: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> float:
        """
        Count tokens, compute cost, persist to SQLite, return cost.
        """
        if input_tokens is None:
            input_tokens = _count_tokens(input_text, model)
        if output_tokens is None:
            output_tokens = _count_tokens(output_text, model)

        cost = self.estimate_cost(model, input_tokens, output_tokens)
        self._session_cost += cost

        now = datetime.utcnow().isoformat()
        preview = (input_text[:120] + "…") if len(input_text) > 120 else input_text

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO cost_log (timestamp, model, input_tokens, output_tokens,
                                          cost_usd, conversation_id, prompt_preview)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (now, model, input_tokens, output_tokens, cost, conversation_id, preview),
                )
                await db.commit()
        except Exception as exc:
            logger.error("Failed to persist cost log: {}", exc)

        logger.info(
            "COST | model={} in={} out={} cost=${:.6f} session_total=${:.4f}",
            model,
            input_tokens,
            output_tokens,
            cost,
            self._session_cost,
        )
        return cost

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    async def get_cost_summary(self) -> Dict[str, Any]:
        """High-level cost summary for the dashboard."""
        budget = await self.check_budget()
        return {
            "session_cost": round(self._session_cost, 6),
            **budget,
            "daily_budget": self.daily_budget,
            "monthly_budget": self.monthly_budget,
        }

    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """Public helper to count tokens."""
        return _count_tokens(text, model)
