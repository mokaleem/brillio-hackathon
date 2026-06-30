from __future__ import annotations

from typing import Any


def summarize_metrics(rows: list[dict[str, Any]], metric: str = "value") -> dict[str, Any]:
    values = [float(row.get(metric, 0)) for row in rows]
    total = sum(values)
    return {
        "count": len(values),
        "total": total,
        "average": total / len(values) if values else 0,
    }
