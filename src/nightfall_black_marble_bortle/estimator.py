from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

NASA_BLACK_MARBLE_V1 = "nasa_black_marble_v1"


@dataclass(frozen=True)
class BortleEstimate:
    bortle_class: int
    estimate: float
    source: str
    model_version: str
    feature_value: float


def clamp_bortle(value: float) -> float:
    return max(1.0, min(9.0, value))


def _shape(array: Any) -> tuple[int, int]:
    shape = getattr(array, "shape", None)
    if shape and len(shape) >= 2:
        return int(shape[0]), int(shape[1])
    return len(array), len(array[0]) if array else 0


def _is_valid_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _cell_value(array: Any, row: int, col: int) -> Any:
    try:
        return array[row, col]
    except (TypeError, IndexError):
        return array[row][col]


def _median(values: list[float]) -> float:
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2


def _feature_to_bortle_estimate(feature_value: float, *, intercept: float, slope: float) -> float:
    return clamp_bortle(intercept + slope * math.log10(max(feature_value, 0.1)))


def _cell_feature_value(median_grid: Any, mean_grid: Any, count_grid: Any, row: int, col: int) -> float | None:
    count_value = _cell_value(count_grid, row, col)
    if not _is_valid_number(count_value) or float(count_value) <= 0:
        return None
    median_value = _cell_value(median_grid, row, col)
    mean_value = _cell_value(mean_grid, row, col)
    if not _is_valid_number(median_value) or not _is_valid_number(mean_value):
        return None
    return (float(median_value) + float(mean_value)) / 2


@lru_cache(maxsize=2)
def load_grid(grid_path: str) -> dict[str, Any]:
    import numpy as np

    path = Path(grid_path)
    if not path.exists():
        raise FileNotFoundError(grid_path)
    with np.load(path) as grid:
        return {
            "median": grid["median"],
            "mean": grid["mean"],
            "count": grid["count"],
            "resolution_deg": float(grid["resolution_deg"]),
            "west": float(grid["west"]),
            "north": float(grid["north"]),
        }


def estimate_bortle(
    latitude: float,
    longitude: float,
    *,
    grid_path: str,
    radius_cells: int = 1,
    intercept: float = 5.1536243743513115,
    slope: float = 2.2250785837834295,
) -> BortleEstimate | None:
    grid = load_grid(grid_path)
    median_grid = grid["median"]
    mean_grid = grid["mean"]
    count_grid = grid["count"]
    resolution_deg = float(grid["resolution_deg"])
    west = float(grid["west"])
    north = float(grid["north"])
    height, width = _shape(median_grid)
    if height <= 0 or width <= 0 or resolution_deg <= 0:
        return None

    south = north - height * resolution_deg
    east = west + width * resolution_deg
    if latitude > north or latitude < south or longitude < west or longitude > east:
        return None

    row = min(height - 1, max(0, int(math.floor((north - latitude) / resolution_deg))))
    col = min(width - 1, max(0, int(math.floor((longitude - west) / resolution_deg))))

    median_values: list[float] = []
    mean_values: list[float] = []
    for sample_row in range(max(0, row - radius_cells), min(height, row + radius_cells + 1)):
        for sample_col in range(max(0, col - radius_cells), min(width, col + radius_cells + 1)):
            count_value = _cell_value(count_grid, sample_row, sample_col)
            if not _is_valid_number(count_value) or float(count_value) <= 0:
                continue
            median_value = _cell_value(median_grid, sample_row, sample_col)
            mean_value = _cell_value(mean_grid, sample_row, sample_col)
            if _is_valid_number(median_value):
                median_values.append(float(median_value))
            if _is_valid_number(mean_value):
                mean_values.append(float(mean_value))

    if not median_values or not mean_values:
        return None

    feature_value = (_median(median_values) + sum(mean_values) / len(mean_values)) / 2
    raw_estimate = _feature_to_bortle_estimate(feature_value, intercept=intercept, slope=slope)

    center_feature_value = _cell_feature_value(median_grid, mean_grid, count_grid, row, col)
    if center_feature_value is not None:
        center_estimate = _feature_to_bortle_estimate(center_feature_value, intercept=intercept, slope=slope)
        # Do not let a median-heavy neighborhood make a locally lit town look
        # like dark sky. Keep neighborhood smoothing for moderate/bright areas.
        if raw_estimate < 4.0 <= center_estimate:
            feature_value = center_feature_value
            raw_estimate = center_estimate

    return BortleEstimate(
        bortle_class=int(round(raw_estimate)),
        estimate=raw_estimate,
        source=NASA_BLACK_MARBLE_V1,
        model_version=NASA_BLACK_MARBLE_V1,
        feature_value=feature_value,
    )
