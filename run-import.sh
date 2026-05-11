#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 pipeline.py --config lists.json "$@"
echo
read -p "--- Done. Press Enter to close ---"
