"""Runs every test file and prints one line per file.

    python tests/run_all.py              everything
    python tests/run_all.py --headless   only what runs without a desktop

None of them spend tokens or touch the network: the engines are faked and the
window runs against a stand-in. A game the player saved earlier is used read-only.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# These three open real Tk windows. They pass on a desktop, but a build server may
# have no session to open them in, which is what --headless is for.
NEEDS_DISPLAY = {"test_gui.py", "test_scrolling.py", "test_without_anthropic.py"}

HEADLESS = "--headless" in sys.argv
TESTS = sorted(name for name in os.listdir(HERE)
               if name.startswith("test_") and name.endswith(".py"))

failed, skipped, checks = [], [], 0
for name in TESTS:
    if HEADLESS and name in NEEDS_DISPLAY:
        skipped.append(name)
        print(f"SKIP  {name:34}  needs a desktop")
        continue

    result = subprocess.run([sys.executable, os.path.join(HERE, name)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    passed = sum(1 for line in (result.stdout or "").splitlines() if line.startswith("PASS"))
    checks += passed
    status = "OK  " if result.returncode == 0 else "FAIL"
    print(f"{status}  {name:34} {passed:3} checks")
    if result.returncode != 0:
        failed.append(name)
        for line in (result.stdout or "").splitlines():
            if line.startswith("FAIL"):
                print("        " + line)
        if result.stderr.strip():
            print("        " + result.stderr.strip().splitlines()[-1])

print()
print(f"{checks} checks" + (f", {len(skipped)} files skipped" if skipped else ""))
print("ALL PASS" if not failed else f"FAILED: {', '.join(failed)}")
sys.exit(0 if not failed else 1)
