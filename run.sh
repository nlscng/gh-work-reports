#!/bin/bash
# Run locally to generate a report using all authenticated gh accounts.
# Usage: ./run.sh [days]       e.g. ./run.sh 7
#        ./run.sh --start YYYY-MM-DD --end YYYY-MM-DD
set -euo pipefail
cd "$(dirname "$0")"

DAYS="${1:-7}"
END=$(date +%Y-%m-%d)
START=$(date -d "$DAYS days ago" +%Y-%m-%d)

# Parse explicit start/end if provided
if [[ "${1:-}" == "--start" ]]; then
    START="$2"
    END="$4"
fi

OUTFILE="docs/reports/report-${START}-to-${END}.md"

echo "=== Generating report: ${START} → ${END} ==="

# Detect all authenticated accounts
ACCOUNTS=$(gh auth status 2>&1 | grep -oP 'Logged in to github.com account \K\S+' || true)
ORIGINAL=$(gh auth status 2>&1 | grep -oP 'Logged in to github.com account \K\S+' | head -1)

if [[ -z "$ACCOUNTS" ]]; then
    echo "No gh accounts found. Run: gh auth login"
    exit 1
fi

# For multi-account: generate per-account, then pick the work account result
# (The generate-report.py filters to cloud-ecosystem-security/* anyway)
echo "Using account: $(gh auth status 2>&1 | grep 'account' | head -1)"

python3 scripts/generate-report.py --start "$START" --end "$END" --output "$OUTFILE"
python3 scripts/build-html.py

echo ""
echo "=== Done ==="
echo "Markdown: $OUTFILE"
echo "View: open docs/index.html"
