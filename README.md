# Nightfall Black Marble Bortle

Private working repo for Nightfall's NASA Black Marble derived Bortle estimator.

Current status: private, experimental, and not yet ready for public release.

## What Belongs Here

- Runtime lookup code for compact NASA Black Marble derived grids.
- Reproducible ingest/derivation scripts.
- Model metadata and provenance notes.
- Synthetic tests and tiny fixtures.
- Documentation for artifact boundaries and NASA attribution.

## What Does Not Belong Here

- Raw NASA HDF5 tiles.
- Earthdata/LAADS tokens, cookies, credentials, or request logs.
- Lightpollutionmap.app labels, screenshots, or scraped data.
- Private support coordinates or user-specific benchmark rows.
- Large compact grid artifacts committed to Git history.

Large derived grids should be published later as private release assets or object storage artifacts with checksums and provenance.

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
- Feature: median/mean blend
- Formula: `clamp(intercept + slope * log10(max(feature, 0.1)), 1, 9)`
- Intercept: `5.1536243743513115`
- Slope: `2.2250785837834295`

## Attribution

This project uses derived data from NASA Black Marble / VIIRS nighttime-light products. NASA endorsement is not implied.
