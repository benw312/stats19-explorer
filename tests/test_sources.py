import hashlib

import httpx
import pytest

from stats19.download import download_file
from stats19.sources import CONTENT_API_URL, SourceError, fetch_release, parse_release

BASE = "https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics"
ASSETS = "https://assets.publishing.service.gov.uk/media"


def _content(body: str, attachments: list[dict] | None = None) -> dict:
    return {
        "public_updated_at": "2026-07-30T09:30:07+01:00",
        "details": {"body": body, "attachments": attachments or []},
    }


FULL_BODY = f"""
<a href="{BASE}-collision-1979-latest-published-year.csv">c</a>
<a href="{BASE}-vehicle-1979-latest-published-year.csv">v</a>
<a href="{BASE}-casualty-1979-latest-published-year.csv">k</a>
<a href="{BASE}-collision-last-5-years.csv">5y</a>
<a href="{ASSETS}/aaa/dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2024.xlsx">old</a>
<a href="{ASSETS}/bbb/dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2025.xlsx">new</a>
"""


def test_parse_release_finds_full_history_files_and_newest_guide():
    release = parse_release(_content(FULL_BODY))

    assert release.public_updated_at == "2026-07-30T09:30:07+01:00"
    assert release.csv_urls == {
        "collision": f"{BASE}-collision-1979-latest-published-year.csv",
        "vehicle": f"{BASE}-vehicle-1979-latest-published-year.csv",
        "casualty": f"{BASE}-casualty-1979-latest-published-year.csv",
    }
    assert release.guide_url.endswith("data-guide-2025.xlsx")


def test_parse_release_reads_attachment_urls_too():
    body = FULL_BODY.replace("data-guide-2025", "x").replace("data-guide-2024", "y")
    attachments = [{"url": f"{ASSETS}/ccc/road-safety-open-dataset-data-guide-2026.xlsx"}]

    release = parse_release(_content(body, attachments))

    assert release.guide_url.endswith("data-guide-2026.xlsx")


def test_parse_release_raises_when_a_table_is_missing():
    body = FULL_BODY.replace("vehicle-1979", "nope")

    with pytest.raises(SourceError, match="vehicle"):
        parse_release(_content(body))


def test_parse_release_raises_when_guide_missing():
    body = FULL_BODY.replace(".xlsx", ".pdf")

    with pytest.raises(SourceError, match="data guide"):
        parse_release(_content(body))


def test_fetch_release_calls_content_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == CONTENT_API_URL
        return httpx.Response(200, json=_content(FULL_BODY))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        release = fetch_release(client)

    assert release.csv_urls["casualty"].endswith("casualty-1979-latest-published-year.csv")


def test_download_file_streams_to_disk_and_hashes(tmp_path):
    payload = b"collision_index,collision_year\n2025X,2025\n" * 1000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = download_file(client, "https://example.org/data/file.csv", tmp_path)

    assert result.path == tmp_path / "file.csv"
    assert result.path.read_bytes() == payload
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.size_bytes == len(payload)
    assert not list(tmp_path.glob("*.part"))


def test_download_file_raises_on_http_error_and_leaves_no_partial(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        download_file(client, "https://example.org/file.csv", tmp_path)

    assert list(tmp_path.iterdir()) == []
