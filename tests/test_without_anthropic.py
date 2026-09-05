"""The game has to start for someone who only has a Claude subscription.

The anthropic package is needed for the API path alone, but it used to be imported
at the top of the window, so a player without it could not even open the game.
Nothing on this machine can prove that: the package is installed. So the checks
below run in a separate interpreter with a stub that refuses to import.
"""

import os
import subprocess
import sys
import tempfile

from harness import check, finish

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A module of this name earlier on the path makes `import anthropic` fail the same
# way a missing package does.
stub_dir = tempfile.mkdtemp()
with open(os.path.join(stub_dir, "anthropic.py"), "w", encoding="utf-8") as f:
    f.write('raise ImportError("No module named \'anthropic\' (test stub)")\n')


def run(code):
    """Runs code in a fresh interpreter that cannot import anthropic."""
    environment = dict(os.environ, PYTHONPATH=stub_dir + os.pathsep + PROJECT,
                       ANTHROPIC_API_KEY="")
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=PROJECT, env=environment)


result = run("import anthropic")
check("the stub really blocks the package", result.returncode != 0, result.stderr[-80:])

result = run("from game import engine_api; print('AVAILABLE', engine_api.AVAILABLE)")
check("engine_api imports without the package", result.returncode == 0, result.stderr[-200:])
check("and reports that the API path is closed", "AVAILABLE False" in result.stdout,
      result.stdout.strip())

result = run("from game import gui; print('TITLE', gui.TITLE)")
check("the window module imports without the package", result.returncode == 0,
      result.stderr[-200:])

result = run(
    "from game import gui\n"
    "app = gui.AdventureWindow()\n"
    "app.update()\n"
    "print('WINDOW', app.title())\n"
    "app.destroy()\n"
)
check("the window opens without the package", result.returncode == 0, result.stderr[-300:])
check("and it is the right window", "WINDOW The Narrator" in result.stdout,
      result.stdout.strip())

# With no Claude Code either, the player deserves an explanation rather than a crash.
result = run(
    "from game import gui\n"
    "gui.BACKEND = 'api'\n"
    "shown = []\n"
    "gui.messagebox = type('Quiet', (), {'showerror': staticmethod(lambda t, m: shown.append(m)),"
    " 'showinfo': staticmethod(lambda *a: None), 'askyesno': staticmethod(lambda *a: True)})\n"
    "app = gui.AdventureWindow()\n"
    "app.update()\n"
    "print('STARTED', app.select_backend('brief'))\n"
    "print('SAID', shown[0].replace(chr(10), ' ') if shown else '')\n"
    "app.destroy()\n"
)
check("starting a game says no instead of crashing", result.returncode == 0, result.stderr[-300:])
check("it refuses to start", "STARTED False" in result.stdout, result.stdout.strip())
check("and names the missing package", "pip install anthropic" in result.stdout,
      result.stdout.strip())

# The terminal front-end is API-only, so there it may refuse -- but politely.
result = run("from game import console; console.main()")
check("the terminal version explains itself", "pip install anthropic" in (result.stdout + result.stderr),
      (result.stdout + result.stderr).strip()[-120:])

finish()
