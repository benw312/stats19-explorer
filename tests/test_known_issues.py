"""DfT's documented data issues (FU-049)."""

from stats19.known_issues import BY_ID, ISSUES, issues_for


def test_issues_match_the_force_and_years_they_cover():
    got = issues_for([(21, 2016), (21, 2018), (21, 2023), (52, 2022), (52, 2023), (1, 2022)])

    assert got == {"staffordshire-2017-2023": [2018, 2023], "avon-somerset-2022": [2022]}


def test_a_welsh_force_gets_the_speed_limit_coding_issue():
    got = issues_for([(62, 2023)])

    assert list(got) == ["wales-speed-limit-2023"]
    assert BY_ID["wales-speed-limit-2023"].affects == "speed_limit"


def test_every_issue_has_dft_wording_and_a_unique_id():
    assert len({i.id for i in ISSUES}) == len(ISSUES)
    assert all(i.dft_text and i.summary and i.year_from <= i.year_to for i in ISSUES)
