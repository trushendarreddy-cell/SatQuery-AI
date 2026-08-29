"""Deterministic seasonal false-positive risk from acquisition dates only."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from app.pipeline.scene_classifier import SceneClassifier
from app.schemas.analysis_schema import SeasonalRisk

SAME_WINDOW_DAYS = 30
OPPOSITE_SEASON_DAYS = 120


def day_of_year_delta(dt1: datetime, dt2: datetime) -> int:
    d1 = dt1.timetuple().tm_yday
    d2 = dt2.timetuple().tm_yday
    raw = abs(d1 - d2)
    return int(min(raw, 365 - raw))


def evaluate_seasonal_risk(
    date_1: Optional[str],
    date_2: Optional[str],
) -> Tuple[SeasonalRisk, Optional[bool], Optional[int], Optional[float], str]:
    """
    Returns (risk, same_window, doy_delta, time_delta_days, explanation).
    Does not classify change as a real event.
    """
    dt1 = SceneClassifier._parse_timestamp(date_1) if date_1 else None
    dt2 = SceneClassifier._parse_timestamp(date_2) if date_2 else None

    if not dt1 or not dt2:
        return (
            SeasonalRisk.UNKNOWN,
            None,
            None,
            None,
            "Acquisition dates are missing; seasonal false-positive risk cannot be assessed.",
        )

    if dt1 <= dt2:
        delta_days = (dt2 - dt1).total_seconds() / 86400.0
    else:
        delta_days = (dt1 - dt2).total_seconds() / 86400.0

    doy_delta = day_of_year_delta(dt1, dt2)
    same_window = doy_delta <= SAME_WINDOW_DAYS

    if delta_days < 1.0:
        risk = SeasonalRisk.NONE
        explanation = "Scenes are near-simultaneous; seasonal vegetation cycle is not a factor."
    elif same_window:
        risk = SeasonalRisk.LOW
        explanation = (
            f"Day-of-year offset is {doy_delta} days (same phenological window). "
            "Seasonal green-up/senescence is less likely to dominate, but change is not confirmed as a real event."
        )
    elif doy_delta >= OPPOSITE_SEASON_DAYS:
        risk = SeasonalRisk.HIGH
        explanation = (
            f"Day-of-year offset is {doy_delta} days (opposite-season window). "
            "Apparent change may be seasonal; it is not treated as a confirmed real event."
        )
    else:
        risk = SeasonalRisk.MODERATE
        explanation = (
            f"Day-of-year offset is {doy_delta} days. Seasonal effects are possible; "
            "change is not treated as a confirmed real event."
        )

    return risk, same_window, doy_delta, round(float(delta_days), 2), explanation
