#!/usr/bin/env bash
# new-prd.sh — Scaffold a new PRD from the canonical template.
#
# Usage:
#   ./new-prd.sh "Feature name"
#   ./new-prd.sh "Feature name" ~/docs/prds
#
# Creates: <out-dir>/prd-<kebab-case-name>-YYYY-MM-DD.md

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 \"Feature name\" [output-dir]" >&2
  exit 1
fi

NAME="$1"
OUT_DIR="${2:-.}"

# kebab-case the name
SLUG=$(echo "$NAME" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-|-$//g')

DATE=$(date +%Y-%m-%d)
OUT_FILE="$OUT_DIR/prd-$SLUG-$DATE.md"

# Locate the template relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../references/prd-template.md"

if [ ! -f "$TEMPLATE" ]; then
  echo "Template not found at: $TEMPLATE" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Substitute the feature name and today's date into the template header
sed -e "s|\[Feature name\]|$NAME|" \
    -e "s|YYYY-MM-DD|$DATE|" \
    "$TEMPLATE" > "$OUT_FILE"

echo "Created: $OUT_FILE"
echo "Next: open it and fill in TL;DR, Problem, and Success metrics before sharing."
