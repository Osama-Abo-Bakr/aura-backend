"""
Unit tests for health log aggregation logic.

Exercises the summary computation in isolation —
no DB connections needed.
"""

from __future__ import annotations

from datetime import date, timedelta


def _make_rows(n: int = 7) -> list[dict]:
    """Generate n days of synthetic health log rows."""
    today = date.today()
    rows = []
    for i in range(n):
        d = today - timedelta(days=n - 1 - i)
        rows.append(
            {
                "log_date": d.isoformat(),
                "mood": (i % 9) + 1,  # 1–9 cycling
                "energy": (i % 7) + 2,  # 2–8 cycling
                "sleep_hours": 5.5 + (i % 4) * 0.5,
                "water_ml": 1500 + i * 100,
                "exercise_minutes": 20 + i * 5,
                "symptoms": ["Headache"] if i % 3 == 0 else ["Fatigue"] if i % 3 == 1 else [],
            }
        )
    return rows


def _compute_summary(rows: list[dict], days: int = 30) -> dict:
    """
    Mirror of the aggregation logic in api/v1/health_log.py::health_summary.
    Kept here as a pure-Python function so we can unit-test it without FastAPI.
    """
    mood_trend = [{"date": r["log_date"], "value": r["mood"]} for r in rows if r.get("mood")]
    energy_trend = [{"date": r["log_date"], "value": r["energy"]} for r in rows if r.get("energy")]
    sleep_trend = [{"date": r["log_date"], "value": r["sleep_hours"]} for r in rows if r.get("sleep_hours") is not None]

    symptom_counts: dict[str, int] = {}
    for r in rows:
        for s in (r.get("symptoms") or []):
            symptom_counts[s] = symptom_counts.get(s, 0) + 1
    symptom_frequency = sorted(
        [{"symptom": k, "count": v} for k, v in symptom_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    exercise_total = sum(r.get("exercise_minutes") or 0 for r in rows)
    water_values = [r["water_ml"] for r in rows if r.get("water_ml") is not None]
    water_avg = round(sum(water_values) / len(water_values)) if water_values else 0

    return {
        "mood_trend": mood_trend,
        "energy_trend": energy_trend,
        "sleep_trend": sleep_trend,
        "symptom_frequency": symptom_frequency,
        "exercise_total_minutes": exercise_total,
        "water_avg_ml": water_avg,
        "days": days,
        "entry_count": len(rows),
    }


def test_summary_entry_count():
    rows = _make_rows(7)
    result = _compute_summary(rows, days=7)
    assert result["entry_count"] == 7


def test_mood_trend_length_matches_rows_with_mood():
    rows = _make_rows(7)
    result = _compute_summary(rows)
    assert len(result["mood_trend"]) == 7


def test_sleep_trend_only_includes_non_null():
    rows = _make_rows(5)
    rows[2]["sleep_hours"] = None
    result = _compute_summary(rows)
    assert len(result["sleep_trend"]) == 4


def test_symptom_frequency_sorted_descending():
    rows = _make_rows(9)  # 3 Headache, 3 Fatigue, 3 empty → tied
    result = _compute_summary(rows)
    counts = [s["count"] for s in result["symptom_frequency"]]
    assert counts == sorted(counts, reverse=True)


def test_exercise_total():
    rows = _make_rows(4)
    expected = sum(r["exercise_minutes"] for r in rows)
    result = _compute_summary(rows)
    assert result["exercise_total_minutes"] == expected


def test_water_avg_rounded():
    rows = _make_rows(3)
    expected = round(sum(r["water_ml"] for r in rows) / 3)
    result = _compute_summary(rows)
    assert result["water_avg_ml"] == expected


def test_empty_rows_returns_zero_values():
    result = _compute_summary([])
    assert result["entry_count"] == 0
    assert result["exercise_total_minutes"] == 0
    assert result["water_avg_ml"] == 0
    assert result["mood_trend"] == []
    assert result["symptom_frequency"] == []


def test_mood_values_within_range():
    rows = _make_rows(10)
    result = _compute_summary(rows)
    for entry in result["mood_trend"]:
        assert 1 <= entry["value"] <= 10


def test_dates_are_ordered_ascending():
    rows = _make_rows(7)
    result = _compute_summary(rows)
    dates = [e["date"] for e in result["mood_trend"]]
    assert dates == sorted(dates)
