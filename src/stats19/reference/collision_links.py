"""Score candidate OS road links for a collision (PLAN-008 T3b).

Follows DfT's 2026 STATS19 network matching feasibility study: candidate links within
25 m, each scored on distance, road number (exact, special cases such as the M6 Toll,
unnumbered-to-unnumbered, and limited fuzzy matching), road class, and form of way
(roundabout, dual, single, slip). The best score wins, then the nearer link. DfT doesn't
publish its weights, only that 100+ is "good" (93% judged good) and under 75 needs review,
so ours are set so a close match on the right road number and class scores 100+.

Pure functions, so the rules are unit-tested without a database.
"""

from __future__ import annotations

from dataclasses import dataclass

CANDIDATE_RADIUS_M = 25.0
GOOD_SCORE = 100
REVIEW_BELOW = 75

# At the collision point, falling to 0 at 25 m. Quadratic: police locations on a dual
# carriageway sit ~5-10 m off OS's centreline, which shouldn't cost much, while a link
# near the edge of the search should.
DISTANCE_POINTS = 50.0
NUMBER_EXACT = 40
NUMBER_FUZZY = 15  # one edit apart, same road letter: a likely typo
NUMBER_UNNUMBERED = 35  # police recorded no number (C/U) and the link has none
NUMBER_WRONG = -20
NUMBER_SPURIOUS = -10  # police recorded no number but the link has one
CLASS_MATCH = 15
FORM_MATCH = 15
FORM_WRONG = -10  # a slip road or roundabout link when police recorded neither

# STATS19 first_road_class -> OS road classifications that agree with it. Officers' C and
# unclassified labels often disagree with OS, which is the source of truth for a road's
# class (FU-037 #2): either label agrees with any OS minor road, so among minor roads the
# label never pulls a collision onto a further road.
_MINOR = {"Classified Unnumbered", "Unclassified", "Not Classified", "Unknown"}
_CLASS = {
    1: {"Motorway"},
    2: {"Motorway", "A Road"},  # A(M)
    3: {"A Road"},
    4: {"B Road"},
    5: _MINOR,
    6: _MINOR,
}
# STATS19 road_type -> OS forms of way that agree with it (2 one-way: OS doesn't record it)
_FORM = {
    1: {"Roundabout"},
    3: {"Dual Carriageway", "Collapsed Dual Carriageway"},
    6: {"Single Carriageway"},
    7: {"Slip Road"},
    12: {"Slip Road"},
}
_KNOWN_ROAD_TYPES = {1, 2, 3, 6, 7, 12}
# Police road numbers that OS writes differently
_NUMBER_ALIASES = {"M6": {"M6 TOLL"}}


@dataclass(frozen=True)
class CollisionRoad:
    road_class: int | None  # STATS19 first_road_class
    road_number: int | None  # first_road_number (0 / -1 for unnumbered)
    road_type: int | None  # STATS19 road_type


@dataclass(frozen=True)
class Candidate:
    link_id: str
    distance_m: float
    road_class: str | None
    road_number: str | None
    form_of_way: str | None


@dataclass(frozen=True)
class Match:
    link_id: str
    distance_m: float
    score: float
    margin: float | None  # over the runner-up; None when there was only one candidate


def police_road_number(road_class: int | None, number: int | None) -> str | None:
    """The road number as OS writes it: M5, A1(M), A30, B3212; None for C and U roads."""
    if not number or number <= 0:
        return None
    return {1: f"M{number}", 2: f"A{number}(M)", 3: f"A{number}", 4: f"B{number}"}.get(
        road_class or 0
    )


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _number_points(police: str | None, os_number: str | None) -> int:
    if police is None:
        return NUMBER_UNNUMBERED if os_number is None else NUMBER_SPURIOUS
    if os_number is None:
        return 0
    if os_number == police or os_number in _NUMBER_ALIASES.get(police, set()):
        return NUMBER_EXACT
    if os_number[0] == police[0] and levenshtein(police, os_number) == 1:
        return NUMBER_FUZZY
    return NUMBER_WRONG


def _form_points(road_type: int | None, form: str | None) -> int:
    if form in _FORM.get(road_type or 0, set()):
        return FORM_MATCH
    if road_type in _KNOWN_ROAD_TYPES and form in {"Slip Road", "Roundabout"}:
        return FORM_WRONG
    return 0


def score(road: CollisionRoad, c: Candidate) -> float:
    distance = DISTANCE_POINTS * max(0.0, 1 - (c.distance_m / CANDIDATE_RADIUS_M) ** 2)
    number = _number_points(police_road_number(road.road_class, road.road_number), c.road_number)
    road_class = CLASS_MATCH if c.road_class in _CLASS.get(road.road_class or 0, set()) else 0
    return round(distance + number + road_class + _form_points(road.road_type, c.form_of_way), 2)


def best_match(road: CollisionRoad, candidates: list[Candidate]) -> Match | None:
    """Top score, then nearest, then link id (so reruns agree)."""
    if not candidates:
        return None
    ranked = sorted(
        ((score(road, c), c) for c in candidates),
        key=lambda sc: (-sc[0], sc[1].distance_m, sc[1].link_id),
    )
    top, best = ranked[0]
    margin = round(top - ranked[1][0], 2) if len(ranked) > 1 else None
    return Match(best.link_id, best.distance_m, top, margin)
