"""Minor-road stretch rules (PLAN-008 T2) on small hand-built networks."""

from stats19.reference.stretch import Link, grow_stretch, same_road


def link(id, a, b, length=100.0, road_class="Unclassified", number=None, name=None):
    return Link(id, road_class, number, name, a, b, length)


def net(*links):
    return {lk.id: lk for lk in links}


# A B road running n0-n1-n2-n3-n4 (each 100 m), the count point on b2 (n1-n2).
def b_road(**over):
    return [
        link(f"b{i}", f"n{i - 1}", f"n{i}", road_class="B Road", number="B3212")
        for i in range(1, 5)
    ]


def test_continues_through_lower_class_side_roads_and_stops_at_road_end():
    links = net(*b_road(), link("side", "n2", "s1", road_class="Unclassified", name="Mill Lane"))

    got = grow_stretch(links["b2"], 0.5, links)

    assert set(got) == {"b1", "b2", "b3", "b4"}
    assert got["b2"] == 0.0
    assert got["b3"] == 50.0  # from the count point to n2
    assert got["b4"] == 150.0


def test_stops_at_junction_with_equal_or_higher_class():
    links = net(*b_road(), link("a", "n3", "x", road_class="A Road", number="A30"))

    got = grow_stretch(links["b2"], 0.5, links)

    assert set(got) == {"b1", "b2", "b3"}  # b4 is beyond the A-road junction at n3


def test_crossing_b_road_also_stops_it():
    links = net(*b_road(), link("other", "n1", "y", road_class="B Road", number="B3174"))

    assert set(grow_stretch(links["b2"], 0.5, links)) == {"b2", "b3", "b4"}


def test_named_road_stops_where_the_name_changes():
    links = net(
        link("r1", "n0", "n1", name="High Street"),
        link("r2", "n1", "n2", name="High Street"),
        link("r3", "n2", "n3", name="Station Road"),
    )

    assert set(grow_stretch(links["r1"], 0.5, links)) == {"r1", "r2"}


def test_unnamed_road_only_continues_through_simple_joins():
    links = net(
        link("u1", "n0", "n1"),
        link("u2", "n1", "n2"),  # n1 has degree 2: continue
        link("u3", "n2", "n3"),
        link("spur", "n2", "z"),  # n2 is a 3-way junction of equal class: stop
    )

    assert set(grow_stretch(links["u1"], 0.5, links)) == {"u1", "u2"}


def lane(id, a, b, start_bearing, road_class="Unclassified"):
    # leaving a at start_bearing; a straight link leaves b the opposite way
    return Link(
        id,
        road_class,
        None,
        "Nurstead Lane",
        a,
        b,
        100.0,
        start_bearing,
        (start_bearing + 180) % 360,
    )


def test_same_named_fork_follows_the_branch_most_in_line():
    # FU-034 #2: heading east into n1, the lane forks: straight on (east) and a spur north
    links = net(
        lane("in", "n0", "n1", 90),
        lane("ahead", "n1", "n2", 100),
        lane("spur", "n1", "s1", 10),
        lane("spur2", "s1", "s2", 0),
    )

    assert set(grow_stretch(links["in"], 0.5, links)) == {"in", "ahead"}


def test_same_named_fork_prefers_the_branch_of_the_same_class():
    # OS often classes a same-named spur (a farm or estate road) "Unknown"
    links = net(
        lane("in", "n0", "n1", 90),
        lane("bend", "n1", "n2", 30),
        lane("spur", "n1", "s1", 95, road_class="Unknown"),
    )

    assert set(grow_stretch(links["in"], 0.5, links)) == {"in", "bend"}


def test_carriageways_splitting_ahead_are_both_followed():
    links = net(
        lane("in", "n0", "n1", 90),
        lane("left", "n1", "n2", 75),
        lane("right", "n1", "n3", 105),
    )

    assert set(grow_stretch(links["in"], 0.5, links)) == {"in", "left", "right"}


def test_distance_cap_limits_each_direction():
    road = [link(f"r{i}", f"n{i}", f"n{i + 1}", length=400.0, name="Long Lane") for i in range(6)]
    links = net(*road)

    got = grow_stretch(links["r2"], 0.0, links, max_m=1000.0)

    # from n2: back r1 (0), r0 (400); forward r3 (400), r4 (800); r5 starts at 1200 m
    assert set(got) == {"r0", "r1", "r2", "r3", "r4"}


def test_same_road_rules():
    b = link("b", "a", "b", road_class="B Road", number="B1")
    assert same_road(b, link("x", "b", "c", road_class="B Road", number="B1"), 3)
    assert not same_road(b, link("x", "b", "c", road_class="B Road", number="B2"), 2)
    named = link("n", "a", "b", name="Elm Road")
    assert same_road(named, link("x", "b", "c", name="Elm Road"), 4)
    assert not same_road(named, link("x", "b", "c", name="Elm Road", number="B9"), 2)
    plain = link("p", "a", "b")
    assert same_road(plain, link("x", "b", "c"), 2)
    assert not same_road(plain, link("x", "b", "c", road_class="Not Classified"), 2)
