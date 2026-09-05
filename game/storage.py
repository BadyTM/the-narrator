"""Saving and loading a game.

One file holds the whole game: the transcript, the world settings and the id of the
Claude Code session it came from. Saves live in a folder of their own next to the
program, so the game's own files stay out of the way of the code.

SAVE_PATH is module-level on purpose: it is derived from this file's own location, so
it is right whatever folder the game was started from, and the tests point it at a
temporary folder instead.

This module deals in plain JSON only. Turning the settings into a world.Settings
record is the caller's job, so a broken file surfaces as one clear error there.
"""

import json
import os
from datetime import datetime

from . import ROOT

SAVES_DIR = os.path.join(ROOT, "saves")
SAVE_PATH = os.path.join(SAVES_DIR, "adventure_save.json")


def _print(text):
    print(text)


def save(messages, announce=_print, session_id=None, settings=None):
    """Writes the game to SAVE_PATH. `settings` is a world.Settings record."""
    data = {"saved_at": datetime.now().isoformat(timespec="seconds"), "messages": messages}
    if settings is not None:
        data["settings"] = settings.to_json()
    if session_id:
        # With Claude Code the conversation lives in its session; we keep a pointer
        # to it so a loaded game can say which session it came from.
        data["session_id"] = session_id
    # The folder may not exist yet -- on a fresh copy of the game, or after someone
    # deleted their old saves.
    os.makedirs(os.path.dirname(SAVE_PATH) or ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    announce(f"[Ulozeno do {SAVE_PATH}]")


def load(announce=_print):
    """Returns the whole saved game (messages, settings, session_id), or None."""
    if not os.path.exists(SAVE_PATH):
        announce(f"[Soubor {SAVE_PATH} neexistuje]")
        return None
    with open(SAVE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    announce(f"[Nactena hra ulozena {data['saved_at']}]")
    return data


def load_messages(announce=_print):
    """Just the transcript of a saved game, or None."""
    data = load(announce)
    return data["messages"] if data else None
