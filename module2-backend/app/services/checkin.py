from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.models.risk_signal import RiskSeverity, RiskSignalType


EARTH_RADIUS_METERS = 6_371_000.0


def haversine_distance_meters(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """Return the great-circle distance between two WGS84 coordinates."""

    latitude_delta = radians(latitude_2 - latitude_1)
    longitude_delta = radians(longitude_2 - longitude_1)
    first_latitude = radians(latitude_1)
    second_latitude = radians(latitude_2)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(first_latitude)
        * cos(second_latitude)
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(haversine))


@dataclass(frozen=True)
class InitialRiskFactor:
    signal_type: RiskSignalType
    severity: RiskSeverity
    weight: float
    confidence: float = 1.0
    details: dict[str, Any] | None = None

    def public_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "type": self.signal_type.value,
            "severity": self.severity.value,
            "weight": self.weight,
            "confidence": self.confidence,
        }
        if self.details is not None:
            value["details"] = self.details
        return value


def initial_risk_score(factors: list[InitialRiskFactor]) -> float:
    return round(min(sum(factor.weight * factor.confidence for factor in factors), 1.0), 4)
