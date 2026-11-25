"""Typed research-signal responses (issue #19 phase 5).

No model is approved, so every supported stock answers with a typed
"unavailable" response. Nothing here trains, scores or stores predictions, and
there is no fixture fallback: an available signal can exist only after a
separately approved model, artifact and persistence layer (see docs/ML_*).
The schema follows docs/FRONTEND_ML_INTEGRATION_SPEC.md section 4.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator

SCHEMA_VERSION = "1"
# Only the next-session horizon is defined by the research spec. Other values are
# rejected (422), never silently mapped to a different horizon.
SUPPORTED_HORIZONS = (1,)
UnavailableReason = Literal[
    "model_not_approved",
    "insufficient_history",
    "input_not_settled",
    "stale_batch",
    "incompatible_artifact",
]
MESSAGES = {
    "model_not_approved": "No approved model signal is available.",
}
SIGNAL_FIELDS = (
    "target_kind",
    "as_of_session",
    "target_session",
    "published_at",
    "direction",
    "raw_score",
    "probability",
    "signal_strength",
    "universe_percentile",
    "risk_level",
    "model_version",
    "data_snapshot",
    "provenance",
)


class SignalResponse(BaseModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    ticker: str
    status: Literal["available", "unavailable"]
    unavailable_reason: UnavailableReason | None
    message: str | None
    target_kind: str | None = None
    horizon_sessions: int
    as_of_session: date | None = None
    target_session: date | None = None
    published_at: datetime | None = None
    direction: str | None = None
    raw_score: float | None = None
    probability: float | None = None
    signal_strength: str | None = None
    universe_percentile: float | None = None
    risk_level: str | None = None
    model_version: str | None = None
    data_snapshot: str | None = None
    provenance: str | None = None

    @model_validator(mode="after")
    def consistent_status(self):
        # An unavailable response carries a reason and no signal values; an
        # available one needs its dates, target and provenance. Zero is a value
        # and null is "unavailable": they are never interchangeable.
        if self.status == "unavailable":
            if self.unavailable_reason is None or any(
                getattr(self, field) is not None for field in SIGNAL_FIELDS
            ):
                raise ValueError("An unavailable signal carries no signal values.")
        else:
            required = (
                "target_kind",
                "as_of_session",
                "target_session",
                "published_at",
                "model_version",
                "data_snapshot",
                "provenance",
            )
            if self.unavailable_reason is not None or any(
                getattr(self, field) is None for field in required
            ):
                raise ValueError("An available signal needs dates and provenance.")
        return self


def unavailable_signal(symbol: str, horizon_sessions: int) -> SignalResponse:
    reason = "model_not_approved"
    return SignalResponse(
        ticker=symbol,
        status="unavailable",
        unavailable_reason=reason,
        message=MESSAGES[reason],
        horizon_sessions=horizon_sessions,
    )
