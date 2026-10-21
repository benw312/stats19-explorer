"""Streamed downloads with SHA-256, written atomically via a .part file."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class DownloadedFile:
    url: str
    path: Path
    sha256: str
    size_bytes: int


def describe_local_file(path: Path) -> DownloadedFile:
    """Hash an existing file so local loads are recorded like downloads."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_BYTES):
            digest.update(chunk)
    return DownloadedFile(
        url=path.resolve().as_uri(),
        path=path,
        sha256=digest.hexdigest(),
        size_bytes=path.stat().st_size,
    )


def download_file(
    client: httpx.Client, url: str, dest_dir: Path, filename: str | None = None
) -> DownloadedFile:
    """Download to dest_dir/<filename or last URL path segment>."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / (filename or Path(urlparse(url).path).name)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    size = 0

    log.info("downloading %s", url)
    try:
        with client.stream("GET", url) as response, partial.open("wb") as out:
            response.raise_for_status()
            for chunk in response.iter_bytes(CHUNK_BYTES):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    partial.replace(target)
    log.info("downloaded %s (%.1f MB)", target.name, size / 1e6)
    return DownloadedFile(url=url, path=target, sha256=digest.hexdigest(), size_bytes=size)
