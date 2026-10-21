"""Discover the current STATS19 release from the GOV.UK content API.

data.dft.gov.uk sends no ETag/Last-Modified headers, so the page's
``public_updated_at`` is the cheapest change signal. File links come from the
same response, which means a renamed data guide (it gets a new media hash each
year) is picked up automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

CONTENT_API_URL = (
    "https://www.gov.uk/api/content/government/statistical-data-sets/road-safety-open-data"
)

_CSV_RE = re.compile(
    r"https://[^\s\"'<>]*dft-road-casualty-statistics-"
    r"(collision|vehicle|casualty)-1979-latest-published-year\.csv"
)
_GUIDE_RE = re.compile(r"https://[^\s\"'<>]*data-guide-(\d{4})\.xlsx")

TABLE_NAMES = ("collision", "vehicle", "casualty")


class SourceError(RuntimeError):
    """The release page no longer looks the way the pipeline expects."""


@dataclass(frozen=True)
class Release:
    public_updated_at: str
    csv_urls: dict[str, str]
    guide_url: str


def _all_text(content: dict) -> str:
    details = content.get("details", {})
    urls = [a.get("url", "") for a in details.get("attachments", [])]
    return "\n".join([details.get("body", ""), *urls])


def parse_release(content: dict) -> Release:
    text = _all_text(content)

    csv_urls = {m.group(1): m.group(0) for m in _CSV_RE.finditer(text)}
    missing = [t for t in TABLE_NAMES if t not in csv_urls]
    if missing:
        raise SourceError(f"full-history CSV links not found for: {missing}")

    guides = sorted((int(m.group(1)), m.group(0)) for m in _GUIDE_RE.finditer(text))
    if not guides:
        raise SourceError("data guide .xlsx link not found")

    return Release(
        public_updated_at=content["public_updated_at"],
        csv_urls={t: csv_urls[t] for t in TABLE_NAMES},
        guide_url=guides[-1][1],
    )


def fetch_release(client: httpx.Client) -> Release:
    response = client.get(CONTENT_API_URL)
    response.raise_for_status()
    return parse_release(response.json())
