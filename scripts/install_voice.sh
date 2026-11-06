#!/usr/bin/env bash
set -euo pipefail
python -m pip install --no-cache-dir torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install --no-cache-dir -e '.[voice]'
