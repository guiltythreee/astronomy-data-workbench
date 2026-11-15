"""Source manifest and SHA-256 utilities. The source file is only ever read."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceManifest:
    """Where a source file came from. Unknown values stay 'unknown', never guessed."""

    file_name: str
    size_bytes: int
    sha256: str
    source_name: str
    catalogue_release: str = "unknown"
    source_url: str | None = None
    licence_status: str = "unverified"
    acquisition_mode: str = "local-file"
    retrieval_time: str | None = None
    retrieval_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_manifest(
    path: Path,
    source_name: str,
    *,
    catalogue_release: str = "unknown",
    source_url: str | None = None,
    licence_status: str = "unverified",
) -> SourceManifest:
    return SourceManifest(
        file_name=path.name,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        source_name=source_name,
        catalogue_release=catalogue_release,
        source_url=source_url,
        licence_status=licence_status,
    )
