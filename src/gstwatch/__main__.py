"""Allow ``python -m gstwatch``."""
import sys

from .cli import main

sys.exit(main())
