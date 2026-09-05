"""Loads the narrator's house rules from the .md files next to this program.

The reason they live in files: when the narrator misbehaves it is almost always a
matter of wording, not of code. This way the fix is to open a file in Notepad.

Files are sorted by name, so the leading number decides the order (10-, 15-, 20-).
The folder may be missing entirely -- then only the built-in rules apply.

The rule files are written in Czech because the narrator speaks Czech to the player.
"""

import os

from . import ROOT

RULES_DIR = os.path.join(ROOT, "rules")


def rule_files(directory=None):
    """Returns the .md files to load, sorted by name."""
    directory = directory or RULES_DIR
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
            if name.lower().endswith(".md")]


def load(directory=None):
    """Joins every .md file into one block of text for the system prompt."""
    parts = []
    for path in rule_files(directory):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            continue          # an unreadable file must never take the game down
        if text:
            parts.append(text)
    if not parts:
        return ""
    return "\n\n=== DALSI PRAVIDLA ===\n\n" + "\n\n".join(parts)
