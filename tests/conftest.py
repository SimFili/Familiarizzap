from __future__ import annotations

import sys
from pathlib import Path


SPACE_DIR = Path(__file__).resolve().parents[1] / "space"
sys.path.insert(0, str(SPACE_DIR))
