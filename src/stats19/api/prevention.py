"""DfT values of prevention (RAS4001) at the latest prices, for valuing collisions."""

from __future__ import annotations

import psycopg

SEVERITY_NAME = {1: "Fatal", 2: "Serious", 3: "Slight"}


def prevention_values(conn: psycopg.Connection) -> tuple[int | None, dict[int, float]]:
    """(price year, value per reported collision by severity code); zeros if not loaded."""
    rows = conn.execute(
        """SELECT price_year, severity, per_collision FROM geo.value_of_prevention
           WHERE data_year = (SELECT max(data_year) FROM geo.value_of_prevention)"""
    ).fetchall()
    by_name = {r["severity"]: r["per_collision"] for r in rows}
    values = {code: float(by_name.get(name) or 0.0) for code, name in SEVERITY_NAME.items()}
    return (rows[0]["price_year"] if rows else None), values


def value_per_collision(
    observed: int, ksi: int, fatal: int, values: dict[int, float]
) -> float | None:
    """Average value of one collision with this severity mix; None without collisions or prices.

    Used with a peer group's totals: a single site's own mix is too noisy (one fatal
    collision would multiply its value tenfold).
    """
    if observed <= 0 or not any(values.values()):
        return None
    serious = max(ksi - fatal, 0)
    slight = max(observed - ksi, 0)
    total = fatal * values[1] + serious * values[2] + slight * values[3]
    return total / observed
