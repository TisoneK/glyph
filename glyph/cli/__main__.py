"""Enable ``python -m glyph.cli``."""
from __future__ import annotations

import sys

from glyph.cli import main

if __name__ == "__main__":
    sys.exit(main())
