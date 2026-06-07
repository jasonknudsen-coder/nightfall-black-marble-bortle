#!/usr/bin/env bash
set -euo pipefail

# Download and verify a private grid release artifact bundle.
#
# Usage:
#   ./scripts/download_grid_release.sh grid-v2024-001-v0.1.0 [destination]
#
# Requirements:
#   gh with access to jasonknudsen-coder/nightfall-black-marble-bortle
#   shasum or sha256sum

TAG="${1:-}"
DEST="${2:-out/releases/${TAG}}"
REPO="${NIGHTFALL_BLACK_MARBLE_REPO:-jasonknudsen-coder/nightfall-black-marble-bortle}"

if [[ -z "$TAG" ]]; then
  echo "usage: $0 <release-tag> [destination]" >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "FAIL: gh is required to download private GitHub release assets." >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  verify_cmd=(sha256sum -c SHA256SUMS.txt)
elif command -v shasum >/dev/null 2>&1; then
  verify_cmd=(shasum -a 256 -c SHA256SUMS.txt)
else
  echo "FAIL: sha256sum or shasum is required for checksum verification." >&2
  exit 1
fi

mkdir -p "$DEST"

echo "Downloading $REPO@$TAG to $DEST"
gh release download "$TAG" \
  --repo "$REPO" \
  --dir "$DEST" \
  --clobber \
  --pattern 'black_marble_radiance_grid_0p025deg.npz' \
  --pattern 'SHA256SUMS.txt' \
  --pattern 'provenance.json' \
  --pattern 'bortle_model_v1.json'

(
  cd "$DEST"
  "${verify_cmd[@]}"
)

echo "Grid release verified: $TAG"
