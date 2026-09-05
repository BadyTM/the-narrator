"""The game's code. Everything the player touches lives one level up.

    the-narrator/
      The Narrator.pyw           what you double-click
      rules/                     the narrator's house rules, editable prose
      saves/                     saved games
      assets/                    the icon
      game/                      this package
      tests/

Modules here import each other with `from . import ...`, so they run as part of the
package rather than as loose scripts:

    python -m game.gui          the window, with a console for tracebacks
    python -m game.console      the terminal version

ROOT is where those sibling folders live; the modules build their paths from it so
they are right whatever folder the game was started from.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
