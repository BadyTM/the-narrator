"""Saving and loading: where the file lands and what ends up inside it."""

import json
import os
import shutil
import tempfile

from harness import check, finish

from game import storage, world

# --- the default location ---
check("saves live in a folder of their own",
      os.path.basename(os.path.dirname(storage.SAVE_PATH)) == "saves", storage.SAVE_PATH)
check("that folder sits next to the program",
      os.path.dirname(storage.SAVES_DIR)
      == os.path.dirname(os.path.dirname(os.path.abspath(__file__))), storage.SAVES_DIR)
check("the path is absolute, so the working folder cannot move it",
      os.path.isabs(storage.SAVE_PATH), storage.SAVE_PATH)

# --- saving into a folder that does not exist yet ---
sandbox = tempfile.mkdtemp()
storage.SAVE_PATH = os.path.join(sandbox, "saves", "adventure_save.json")
check("the test starts without that folder", not os.path.exists(os.path.dirname(storage.SAVE_PATH)))

messages = [{"role": "user", "content": "Jdu doleva"},
            {"role": "assistant", "content": [{"type": "text", "text": "Stojíš u brány."}]}]
settings = world.Settings(world="Ostrov z ledu a kostí.", genre=world.Genre.FANTASY,
                          players=2, characters=[world.Character("Marek", "zloděj")])
notices = []
storage.save(messages, announce=notices.append, session_id="abc-123", settings=settings)

check("saving creates the folder", os.path.isdir(os.path.dirname(storage.SAVE_PATH)))
check("the file is in it", os.path.exists(storage.SAVE_PATH))
check("the player is told where it went", "saves" in notices[0], notices)

written = json.load(open(storage.SAVE_PATH, encoding="utf-8"))
check("the transcript is saved", written["messages"] == messages)
check("the session id is saved", written["session_id"] == "abc-123")
check("the settings are saved as plain JSON", written["settings"]["genre"] == "fantasy",
      written["settings"])
check("the save is stamped with a time", written["saved_at"][:2] == "20", written["saved_at"])

# --- loading it back ---
loaded = storage.load(announce=lambda _: None)
check("loading returns the transcript", loaded["messages"] == messages)
check("the settings rebuild into a record",
      world.Settings.from_json(loaded["settings"]) == settings)
check("load_messages returns just the transcript",
      storage.load_messages(announce=lambda _: None) == messages)

# --- a missing file is not a crash ---
os.remove(storage.SAVE_PATH)
missing = []
check("a missing save loads as nothing", storage.load(announce=missing.append) is None)
check("and says so", "neexistuje" in missing[0], missing)
check("load_messages agrees", storage.load_messages(announce=lambda _: None) is None)

# --- saving without settings still works (the console game has none) ---
storage.save(messages, announce=lambda _: None)
bare = json.load(open(storage.SAVE_PATH, encoding="utf-8"))
check("a save without settings omits the key", "settings" not in bare, list(bare))

shutil.rmtree(sandbox, ignore_errors=True)
finish()
