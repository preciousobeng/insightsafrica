#!/usr/bin/env bash
# run_full_pipeline.sh
# Runs LTM baseline + anomaly pre-compute for one or more countries.
# Assumes fetch_chirps_archive.py has already completed for these countries.
#
# Usage:
#   bash scripts/run_full_pipeline.sh nigeria ivorycoast senegal capeverde southafrica

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
source venv/bin/activate

COUNTRIES=("$@")
if [ ${#COUNTRIES[@]} -eq 0 ]; then
  echo "Usage: $0 <country> [country ...]"
  exit 1
fi

for country in "${COUNTRIES[@]}"; do
  echo ""
  echo "========================================"
  echo " $country — LTM baseline"
  echo "========================================"
  python3 scripts/compute_ltm_baseline.py --country "$country"

  echo ""
  echo "========================================"
  echo " $country — pre-compute anomalies"
  echo "========================================"
  python3 scripts/precompute_anomalies.py --country "$country"
done

echo ""
echo "All done."
