"""Tiny test helper: no framework, just check() and a summary.

Each test file runs standalone (`python tests/test_dice.py`) and exits non-zero when
something fails, so run_all.py can simply collect exit codes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

_failures = []


def check(name, condition, detail=""):
    """Reports one assertion. `detail` is printed only when it helps explain a failure."""
    print(("PASS  " if condition else "FAIL  ") + name + (f"  {detail}" if detail else ""),
          flush=True)
    if not condition:
        _failures.append(name)


def finish():
    """Prints the verdict and exits with a status run_all.py can read."""
    print("\nALL PASS" if not _failures else f"\nFAILED: {len(_failures)}")
    sys.exit(0 if not _failures else 1)
