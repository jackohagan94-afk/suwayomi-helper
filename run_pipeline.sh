#!/bin/bash
cd /home/jack/suwayomi-helper
rm -f mappings.json report.json pipeline.log
python3 pipeline.py --bind-tracker
