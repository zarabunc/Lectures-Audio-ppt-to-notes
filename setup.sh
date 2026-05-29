#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT}"

mkdir -p input/slides output/notes output/images

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete."
echo ""
echo "  Slides → input/slides/"
echo "  PDF    → output/notes/"
echo "  Images → output/images/  (shared cache)"
echo ""
echo "Run:"
echo "  .venv/bin/python3 merge_notes.py --slides input/slides/your-deck.pdf --name my_lecture_notes"
echo ""
