#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np


PRODUCT = "VNP46A4"
YEAR = 2024
DAY = "001"
COLLECTION = "5200"
VERSION = "002"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "cache"
OUT_DIR = REPO_ROOT / "out"
DEFAULT_DATASET = "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/NearNadir_Composite_Snow_Free"
FILENAME_RE = re.compile(r"\.h(?P<h>\d{2})v(?P<v>\d{2})\.")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_tile(path: Path) -> tuple[int, int]:
    match = FILENAME_RE.search(path.name)
    if not match:
        raise ValueError(f"Cannot parse tile id from {path.name}")
    return int(match.group("h")), int(match.group("v"))


def tile_bounds(h: int, v: int) -> tuple[float, float, float, float]:
    west = -180.0 + h * 10.0
    east = west + 10.0
    north = 90.0 - v * 10.0
    south = north - 10.0
    return west, east, south, north


def scaled_array(dataset: h5py.Dataset) -> np.ndarray:
    arr = dataset[()].astype("float32", copy=False)

    fill = dataset.attrs.get("_FillValue")
    if fill is not None:
        fill_value = np.asarray(fill).reshape(-1)[0]
        arr = np.where(arr == fill_value, np.nan, arr)

    scale = dataset.attrs.get("scale_factor", dataset.attrs.get("ScaleFactor", 1.0))
    offset = dataset.attrs.get("add_offset", dataset.attrs.get("Offset", 0.0))
    scale_value = float(np.asarray(scale).reshape(-1)[0]) if np.asarray(scale).size else 1.0
    offset_value = float(np.asarray(offset).reshape(-1)[0]) if np.asarray(offset).size else 0.0
    if scale_value != 1.0 or offset_value != 0.0:
        arr = arr * scale_value + offset_value

    arr = np.where(np.isfinite(arr) & (arr >= 0), arr, np.nan)
    return arr


def block_stats(arr: np.ndarray, block: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = arr.shape[0] // block
    cols = arr.shape[1] // block
    cropped = arr[: rows * block, : cols * block]
    blocks = cropped.reshape(rows, block, cols, block).swapaxes(1, 2).reshape(rows, cols, block * block)
    valid = np.isfinite(blocks)
    count = valid.sum(axis=2).astype("uint16")
    with np.errstate(all="ignore"):
        median = np.nanmedian(blocks, axis=2).astype("float32")
        mean = np.nanmean(blocks, axis=2).astype("float32")
        p90 = np.nanpercentile(blocks, 90, axis=2).astype("float32")
    median[count == 0] = np.nan
    mean[count == 0] = np.nan
    p90[count == 0] = np.nan
    return median, mean, p90, count


def grid_shape(resolution_deg: float) -> tuple[int, int]:
    lat_cells = int(round(180.0 / resolution_deg))
    lon_cells = int(round(360.0 / resolution_deg))
    return lat_cells, lon_cells


def tile_grid_origin(h: int, v: int, resolution_deg: float) -> tuple[int, int]:
    west, _east, _south, north = tile_bounds(h, v)
    row0 = int(round((90.0 - north) / resolution_deg))
    col0 = int(round((west + 180.0) / resolution_deg))
    return row0, col0


def write_outputs(
    *,
    median: np.ndarray,
    mean: np.ndarray,
    p90: np.ndarray,
    count: np.ndarray,
    resolution_deg: float,
    dataset_path: str,
    processed: list[dict[str, Any]],
    elapsed_seconds: float,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"{resolution_deg:g}deg".replace(".", "p")
    npz_path = OUT_DIR / f"black_marble_radiance_grid_{tag}.npz"
    manifest_path = OUT_DIR / f"black_marble_radiance_grid_{tag}.json"

    np.savez_compressed(
        npz_path,
        median=median,
        mean=mean,
        p90=p90,
        count=count,
        resolution_deg=np.array(resolution_deg, dtype="float32"),
        west=np.array(-180.0, dtype="float32"),
        north=np.array(90.0, dtype="float32"),
    )

    manifest = {
        "artifact": npz_path.name,
        "created_at": now_iso(),
        "product": PRODUCT,
        "year": YEAR,
        "day": DAY,
        "collection": COLLECTION,
        "version": VERSION,
        "dataset": dataset_path,
        "resolution_deg": resolution_deg,
        "grid": {
            "rows": int(median.shape[0]),
            "cols": int(median.shape[1]),
            "west": -180.0,
            "east": 180.0,
            "south": -90.0,
            "north": 90.0,
        },
        "stats": {
            "processed_tiles": len(processed),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "valid_cells": int(np.isfinite(median).sum()),
            "cells_with_observations": int((count > 0).sum()),
        },
        "source_tiles": processed,
        "open_source_hygiene": {
            "inputs": ["NASA LAADS Black Marble VNP46A4"],
            "excludes": [
                "Earthdata/LAADS tokens",
                "proprietary lightpollutionmap.app data",
                "private support/user locations",
                "raw HDF5 files",
            ],
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {npz_path} ({npz_path.stat().st_size / 1024 / 1024:.1f} MiB)", flush=True)
    print(f"wrote {manifest_path}", flush=True)


def run(resolution_deg: float, dataset_path: str, max_tiles: int | None) -> None:
    if not math.isclose(10.0 / resolution_deg, round(10.0 / resolution_deg), rel_tol=0, abs_tol=1e-9):
        raise SystemExit("resolution must evenly divide 10 degrees")

    tile_paths = sorted(CACHE_DIR.glob("*.h5"))
    if max_tiles is not None:
        tile_paths = tile_paths[:max_tiles]
    if not tile_paths:
        raise SystemExit(f"No HDF5 tiles found in {CACHE_DIR}")

    lat_cells, lon_cells = grid_shape(resolution_deg)
    median = np.full((lat_cells, lon_cells), np.nan, dtype="float32")
    mean = np.full((lat_cells, lon_cells), np.nan, dtype="float32")
    p90 = np.full((lat_cells, lon_cells), np.nan, dtype="float32")
    count = np.zeros((lat_cells, lon_cells), dtype="uint16")

    block = int(round(resolution_deg / (10.0 / 2400.0)))
    if block < 1 or 2400 % block != 0:
        raise SystemExit("resolution must align with 2400x2400 10-degree tile pixels")

    processed: list[dict[str, Any]] = []
    start = time.monotonic()
    for index, path in enumerate(tile_paths, start=1):
        h, v = parse_tile(path)
        row0, col0 = tile_grid_origin(h, v, resolution_deg)
        print(f"[{index}/{len(tile_paths)}] {path.name} -> row={row0} col={col0}", flush=True)
        with h5py.File(path, "r") as h5:
            if dataset_path not in h5:
                raise KeyError(f"{dataset_path} not found in {path.name}")
            tile_median, tile_mean, tile_p90, tile_count = block_stats(scaled_array(h5[dataset_path]), block)

        rows, cols = tile_median.shape
        median[row0 : row0 + rows, col0 : col0 + cols] = tile_median
        mean[row0 : row0 + rows, col0 : col0 + cols] = tile_mean
        p90[row0 : row0 + rows, col0 : col0 + cols] = tile_p90
        count[row0 : row0 + rows, col0 : col0 + cols] = tile_count
        west, east, south, north = tile_bounds(h, v)
        processed.append(
            {
                "tile": f"h{h:02d}v{v:02d}",
                "file": path.name,
                "west": west,
                "east": east,
                "south": south,
                "north": north,
                "valid_cells": int(np.isfinite(tile_median).sum()),
            }
        )

    write_outputs(
        median=median,
        mean=mean,
        p90=p90,
        count=count,
        resolution_deg=resolution_deg,
        dataset_path=dataset_path,
        processed=processed,
        elapsed_seconds=time.monotonic() - start,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a compact global Black Marble radiance grid.")
    parser.add_argument("--resolution-deg", type=float, default=0.1)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--max-tiles", type=int, default=None)
    args = parser.parse_args()
    run(args.resolution_deg, args.dataset, args.max_tiles)


if __name__ == "__main__":
    main()
