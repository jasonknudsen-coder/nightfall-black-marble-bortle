from __future__ import annotations

import numpy as np

from nightfall_black_marble_bortle import estimate_bortle


def test_estimate_bortle_from_synthetic_grid(tmp_path):
    grid_path = tmp_path / "synthetic-grid.npz"
    np.savez(
        grid_path,
        median=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float),
        mean=np.array([[2.0, 3.0], [4.0, 5.0]], dtype=float),
        count=np.array([[10, 10], [10, 10]], dtype=float),
        resolution_deg=np.array(1.0),
        west=np.array(-1.0),
        north=np.array(1.0),
    )

    result = estimate_bortle(0.25, -0.25, grid_path=str(grid_path), radius_cells=0)

    assert result is not None
    assert result.source == "nasa_black_marble_v1"
    assert result.model_version == "nasa_black_marble_v1"
    assert result.feature_value == 1.5
    assert result.bortle_class == round(result.estimate)


def test_local_light_signal_is_not_smoothed_into_dark_sky(tmp_path):
    grid_path = tmp_path / "local-light-grid.npz"
    median = np.full((3, 3), 0.01, dtype=float)
    mean = np.full((3, 3), 0.01, dtype=float)
    median[1, 1] = 0.407295
    mean[1, 1] = 0.407295
    np.savez(
        grid_path,
        median=median,
        mean=mean,
        count=np.ones((3, 3), dtype=float),
        resolution_deg=np.array(1.0),
        west=np.array(-1.0),
        north=np.array(1.0),
    )

    result = estimate_bortle(-0.25, 0.25, grid_path=str(grid_path), radius_cells=1)

    assert result is not None
    assert result.bortle_class == 4
    assert result.estimate > 4.0
    assert result.feature_value == median[1, 1]


def test_bright_neighborhood_smoothing_still_prevents_overcorrection(tmp_path):
    grid_path = tmp_path / "bright-neighborhood-grid.npz"
    median = np.full((3, 3), 21.0, dtype=float)
    mean = np.full((3, 3), 21.0, dtype=float)
    median[1, 1] = 33.31
    mean[1, 1] = 33.31
    np.savez(
        grid_path,
        median=median,
        mean=mean,
        count=np.ones((3, 3), dtype=float),
        resolution_deg=np.array(1.0),
        west=np.array(-1.0),
        north=np.array(1.0),
    )

    result = estimate_bortle(-0.25, 0.25, grid_path=str(grid_path), radius_cells=1)

    assert result is not None
    assert result.bortle_class == 8
    assert result.estimate < 8.5
    assert result.feature_value != median[1, 1]


def test_estimate_bortle_returns_none_outside_grid(tmp_path):
    grid_path = tmp_path / "synthetic-grid.npz"
    np.savez(
        grid_path,
        median=np.ones((2, 2), dtype=float),
        mean=np.ones((2, 2), dtype=float),
        count=np.ones((2, 2), dtype=float),
        resolution_deg=np.array(1.0),
        west=np.array(-1.0),
        north=np.array(1.0),
    )

    assert estimate_bortle(20.0, 20.0, grid_path=str(grid_path)) is None
