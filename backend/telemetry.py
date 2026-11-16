import csv
from pathlib import Path
from typing import Any


TELEMETRY_FIELDS = (
    "timestamp", "switch", "port", "link", "tx_mbps", "rx_mbps",
    "tx_pps", "rx_pps", "utilization_pct", "drops", "errors",
)


def _number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_latest(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows[-limit:]:
        normalized = dict(row)
        for field in TELEMETRY_FIELDS:
            if field not in ("timestamp", "switch", "port", "link"):
                normalized[field] = _number(row.get(field, "0"))
        result.append(normalized)
    return result


def summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    if not rows:
        return {"samples": 0, "max_utilization_pct": 0.0, "average_utilization_pct": 0.0}
    utilization = [float(row["utilization_pct"]) for row in rows]
    return {
        "samples": len(rows),
        "max_utilization_pct": round(max(utilization), 2),
        "average_utilization_pct": round(sum(utilization) / len(utilization), 2),
    }

