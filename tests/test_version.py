from stats19.version import version


def test_version_comes_from_the_image(monkeypatch):
    monkeypatch.setenv("STATS19_COMMIT", "18201cc")
    monkeypatch.setenv("STATS19_BUILT", "2026-10-08T20:15Z")

    assert version() == {"commit": "18201cc", "built": "2026-10-08T20:15Z"}


def test_a_dev_checkout_is_unknown(monkeypatch):
    monkeypatch.delenv("STATS19_COMMIT", raising=False)
    monkeypatch.setenv("STATS19_BUILT", "")

    assert version() == {"commit": "unknown", "built": None}
