# Provenance Notes

Current private working model:

- NASA product family: Black Marble / VIIRS nighttime lights
- Product used during Nightfall validation: `VNP46A4`
- Year/day slice used for the first compact grid: `2024-001`
- Local raw archive: kept outside this repo
- Compact grid artifact: kept outside Git history
- Model version: `nasa_black_marble_v1`

## Data Boundaries

This repository should not contain:

- raw HDF5 tiles
- LAADS/Earthdata credentials or request logs
- lightpollutionmap.app labels
- private support coordinates
- large `.npz` grids in normal Git history

## Public Release Checklist

Before making this repo public:

- Confirm NASA citation/acknowledgment wording.
- Decide code license.
- Decide derived artifact hosting and checksums.
- Replace any private validation notes with aggregate-only summaries.
- Re-scan history for accidental large/private data.
