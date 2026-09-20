"""Pure schema/app/capability compatibility decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping


@dataclass(frozen=True)
class CompatibilityDecision:
    compatible: bool
    code: str
    missing_features: tuple[str, ...] = ()


def evaluate_compatibility(
    *,
    database_schema: int,
    app_min_schema: int,
    app_max_schema: int,
    capability_schema: int,
    required_features: Collection[str],
    observed_features: Mapping[str, bool],
    storage_kind: str,
) -> CompatibilityDecision:
    if storage_kind in {"NETWORK", "SYNC", "REMOVABLE", "UNKNOWN"}:
        return CompatibilityDecision(False, "UNSAFE_STORAGE")
    if not app_min_schema <= database_schema <= app_max_schema:
        return CompatibilityDecision(False, "SCHEMA_APP_INCOMPATIBLE")
    if capability_schema != database_schema:
        return CompatibilityDecision(False, "CAPABILITY_SCHEMA_INCOMPATIBLE")
    missing = tuple(sorted(feature for feature in required_features if not observed_features.get(feature, False)))
    if missing:
        return CompatibilityDecision(False, "CAPABILITY_MISSING", missing)
    return CompatibilityDecision(True, "COMPATIBLE")
