"""Byte-budgeted LRU cache for API responses (FU-013)."""

from stats19.api.cache import BytesLRU


def test_hit_and_miss():
    c = BytesLRU(max_bytes=100)
    c.put("a", b"x" * 10)

    assert c.get("a") == b"x" * 10
    assert c.get("b") is None


def test_evicts_least_recently_used_to_stay_within_budget():
    c = BytesLRU(max_bytes=30)
    c.put("a", b"1" * 10)
    c.put("b", b"2" * 10)
    c.put("c", b"3" * 10)
    c.get("a")  # a is now the most recent
    c.put("d", b"4" * 10)

    assert c.get("b") is None
    assert c.get("a") and c.get("c") and c.get("d")
    assert c.size <= 30


def test_items_bigger_than_the_budget_are_not_kept():
    c = BytesLRU(max_bytes=5)
    c.put("big", b"x" * 6)

    assert c.get("big") is None and c.size == 0


def test_replacing_a_key_keeps_the_size_right():
    c = BytesLRU(max_bytes=100)
    c.put("a", b"x" * 40)
    c.put("a", b"x" * 10)

    assert c.size == 10
