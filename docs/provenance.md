# Provenance Notes

Current model:

- NASA product family: Black Marble / VIIRS nighttime lights
- Product used during Nightfall validation: `VNP46A4`
- Year/day slice used for the first compact grid: `2024-001`
- Local raw archive: kept outside this repo
- Compact grid artifact: published as a release asset outside Git history
- Model version: `nasa_black_marble_v1`

## Public Release Checklist

Before publishing a new release:

- Confirm NASA citation/acknowledgment wording.
- Confirm derived artifact hosting and checksums.
- Keep validation notes aggregate-only.
- Re-scan history for accidental large artifacts or sensitive data.
