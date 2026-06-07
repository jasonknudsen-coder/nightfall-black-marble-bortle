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
