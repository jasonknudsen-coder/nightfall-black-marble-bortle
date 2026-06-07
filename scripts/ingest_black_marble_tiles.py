#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PRODUCT = "VNP46A4"
YEAR = 2024
DAY = "001"
COLLECTION = "5200"
VERSION = "002"
BASE = "https://ladsweb.modaps.eosdis.nasa.gov"
LIST_URL = f"{BASE}/api/v2/content/archives/allData/{COLLECTION}/{PRODUCT}/{YEAR}/{DAY}/"
ARCHIVE_URL = f"{BASE}/archive/allData/{COLLECTION}/{PRODUCT}/{YEAR}/{DAY}"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "cache"
OUT_DIR = REPO_ROOT / "out"
MANIFEST_PATH = OUT_DIR / "tile_manifest.json"
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


@dataclass
class TileStatus:
    filename: str
    status: str
    size_bytes: int | None = None
    attempts: int = 0
    last_error: str | None = None
    updated_at: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_token() -> str:
    token = os.environ.get("LAADS_BEARER_TOKEN", "").strip()
    if token:
        return token
    token_file = os.environ.get("LAADS_TOKEN_FILE", "/tmp/key")
    try:
        return Path(token_file).read_text().strip()
    except FileNotFoundError:
        raise SystemExit(
            "Missing LAADS token. Set LAADS_BEARER_TOKEN or write the token to /tmp/key."
        )


def is_hdf5(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(len(HDF5_SIGNATURE)) == HDF5_SIGNATURE
    except FileNotFoundError:
        return False


def load_manifest() -> dict[str, TileStatus]:
    if not MANIFEST_PATH.exists():
        return {}
    raw = json.loads(MANIFEST_PATH.read_text())
    return {name: TileStatus(**data) for name, data in raw.get("tiles", {}).items()}


def write_manifest(manifest: dict[str, TileStatus]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "product": PRODUCT,
        "year": YEAR,
        "day": DAY,
        "collection": COLLECTION,
        "version": VERSION,
        "updated_at": now_iso(),
        "tiles": {name: asdict(status) for name, status in sorted(manifest.items())},
    }
    tmp_path = MANIFEST_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(MANIFEST_PATH)


def list_tiles(session: requests.Session) -> list[str]:
    response = session.get(LIST_URL, timeout=30)
    response.raise_for_status()
    pattern = rf"{PRODUCT}\.A{YEAR}{DAY}\.h\d{{2}}v\d{{2}}\.{VERSION}\.\d+\.h5"
    return sorted(set(re.findall(pattern, response.text)))


def mark(
    manifest: dict[str, TileStatus],
    filename: str,
    status: str,
    *,
    size_bytes: int | None = None,
    error: str | None = None,
) -> None:
    current = manifest.get(filename) or TileStatus(filename=filename, status="pending")
    current.status = status
    current.size_bytes = size_bytes if size_bytes is not None else current.size_bytes
    current.last_error = error
    current.updated_at = now_iso()
    manifest[filename] = current
    write_manifest(manifest)


def download_one(
    session: requests.Session,
    token: str,
    manifest: dict[str, TileStatus],
    filename: str,
    *,
    timeout: int,
    retries: int,
    backoff_seconds: float,
) -> bool:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / filename
    part_path = CACHE_DIR / f"{filename}.part"

    if is_hdf5(path):
        mark(manifest, filename, "cached", size_bytes=path.stat().st_size)
        return True
    if path.exists():
        path.unlink()
    if part_path.exists():
        part_path.unlink()

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{ARCHIVE_URL}/{filename}"
    status = manifest.get(filename) or TileStatus(filename=filename, status="pending")

    for attempt in range(1, retries + 1):
        status.attempts += 1
        manifest[filename] = status
        write_manifest(manifest)
        try:
            with session.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=True) as response:
                response.raise_for_status()
                with part_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            if not is_hdf5(part_path):
                preview = part_path.read_bytes()[:80]
                raise RuntimeError(f"download was not HDF5; first bytes={preview!r}")
            part_path.replace(path)
            mark(manifest, filename, "downloaded", size_bytes=path.stat().st_size)
            return True
        except Exception as exc:  # Keep this script resumable rather than clever.
            part_path.unlink(missing_ok=True)
            error = f"{type(exc).__name__}: {exc}"
            mark(manifest, filename, "error", error=error)
            if attempt >= retries:
                print(f"ERROR {filename}: {error}", flush=True)
                return False
            sleep_for = backoff_seconds * attempt
            print(f"retry {attempt}/{retries - 1} {filename} after {sleep_for:.1f}s: {error}", flush=True)
            time.sleep(sleep_for)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Polite local ingest for NASA LAADS Black Marble tiles.")
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds to sleep between tile downloads.")
    parser.add_argument("--max-files", type=int, default=None, help="Stop after this many newly downloaded files.")
    parser.add_argument("--retries", type=int, default=4, help="Attempts per tile.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout seconds.")
    parser.add_argument("--backoff", type=float, default=30.0, help="Base retry backoff seconds.")
    args = parser.parse_args()

    token = read_token()
    if not token:
        raise SystemExit("Token file/env was empty.")

    session = requests.Session()
    session.headers.update({"User-Agent": "NightfallAtlasLocalBortleSpike/0.1"})

    tiles = list_tiles(session)
    manifest = load_manifest()
    for filename in tiles:
        manifest.setdefault(filename, TileStatus(filename=filename, status="pending", updated_at=now_iso()))
    write_manifest(manifest)

    existing = sum(1 for filename in tiles if is_hdf5(CACHE_DIR / filename))
    print(f"listed={len(tiles)} cached={existing} remaining={len(tiles) - existing}", flush=True)

    downloaded = 0
    failures = 0
    for index, filename in enumerate(tiles, start=1):
        path = CACHE_DIR / filename
        if is_hdf5(path):
            mark(manifest, filename, "cached", size_bytes=path.stat().st_size)
            continue
        if args.max_files is not None and downloaded >= args.max_files:
            break

        print(f"[{index}/{len(tiles)}] download {filename}", flush=True)
        ok = download_one(
            session,
            token,
            manifest,
            filename,
            timeout=args.timeout,
            retries=args.retries,
            backoff_seconds=args.backoff,
        )
        if ok:
            downloaded += 1
        else:
            failures += 1
        if args.sleep > 0:
            time.sleep(args.sleep)

    cached = sum(1 for filename in tiles if is_hdf5(CACHE_DIR / filename))
    total_bytes = sum((CACHE_DIR / filename).stat().st_size for filename in tiles if is_hdf5(CACHE_DIR / filename))
    print(
        f"done listed={len(tiles)} cached={cached} newly_downloaded={downloaded} "
        f"failures={failures} cache_gb={total_bytes / 1024**3:.2f}",
        flush=True,
    )
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
