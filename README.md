# Nightfall Black Marble Bortle

Runtime utilities for Nightfall's NASA Black Marble derived Bortle estimator.

## Overview

This package turns a compact grid derived from NASA Black Marble / VIIRS
nighttime-light data into an approximate Bortle-class estimate for a latitude
and longitude. Nightfall Atlas uses it to give observers a reasonable starting
point for local sky darkness when a saved observing site does not already have a
manual Bortle value.

The estimator is intentionally small: it loads a prebuilt `.npz` grid, samples
nearby radiance cells, blends median and mean brightness, protects against
median-smoothing away local light sources, and maps that feature through the
current `nasa_black_marble_v1` model. The output is a planning aid, not an
official NASA product, a substitute for local observation, or a measured
sky-quality reading.

## What Belongs Here

- Runtime lookup code for compact NASA Black Marble derived grids.
- Reproducible ingest/derivation scripts.
- Model metadata and provenance notes.
- Synthetic tests and tiny fixtures.
- Documentation for artifact boundaries and NASA attribution.

Large derived grids should be published as release assets or object storage artifacts with checksums and provenance.

## Grid Releases

Compact derived grids are versioned as GitHub Release assets, not committed to
Git and not tracked with Git LFS.

Current grid release:

- Tag: `grid-v2024-001-v0.1.0`
- Grid: `black_marble_radiance_grid_0p025deg.npz`
- SHA256: `e161b9115b4d745184271b754e769e8592f16f7afd13a543d5634918966f3913`
- Companion assets: `SHA256SUMS.txt`, `provenance.json`, `bortle_model_v1.json`

Download and verify a release locally:

```bash
./scripts/download_grid_release.sh grid-v2024-001-v0.1.0
```

## Runtime Example

```python
from nightfall_black_marble_bortle import estimate_bortle

result = estimate_bortle(
    39.55388,
    -104.96943,
    grid_path="/path/to/black_marble_radiance_grid_0p025deg.npz",
)
print(result.bortle_class, result.estimate, result.source)
```

## Model V1

- Model name: `nasa_black_marble_v1`
- Grid resolution: `0.025` degree
- Neighborhood radius: `1` cell
- Feature: median/mean blend with exact-cell local-light protection
- Formula: `clamp(intercept + slope * log10(max(feature, 0.1)), 1, 9)`
- Intercept: `5.1536243743513115`
- Slope: `2.2250785837834295`

## Attribution

This project uses derived data from NASA Black Marble / VIIRS nighttime-light products. NASA endorsement is not implied.
