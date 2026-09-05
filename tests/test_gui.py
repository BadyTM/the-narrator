"""The window itself: setup, one turn, error handling, saving and loading.

A fake engine stands in for the network, so nothing here spends tokens. BACKEND is
forced to "api" so the tests never try to launch Claude Code.
"""

import json
import os
import tempfile
import time

from harness import check, finish

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

from game import gui, storage, world

gui.BACKEND = "api"
storage.SAVE_PATH = os.path.join(tempfile.mkdtemp(), "save.json")


class Silent:
    """Message boxes would block a test run, so they always answer yes."""
    askyesno = staticmethod(lambda *a, **k: True)
    showinfo = staticmethod(lambda *a, **k: None)
    showerror = staticmethod(lambda *a, **k: None)


gui.messagebox = Silent


def wait_for_turn(window, seconds=10):
    """Pumps the event loop until the narrator's turn is done.

    Counting update() calls is not enough -- they can all run before the background
    thread has even started, which made this test pass or fail at random.
    """
    deadline = time.time() + seconds
    while window.busy and time.time() < deadline:
        window.update()
        time.sleep(0.02)
    window.update()


class FakeEngine:
    """Records the call and writes a scene, the way a real engine would."""
    calls = []

    @staticmethod
    def narrator_turn(client, messages, costs, write, announce, system=None):
        FakeEngine.calls.append({"system": system, "messages": list(messages)})
        for chunk in ("Stojíš na **rozcestí**. ", "Vlevo mlýn, vpravo les."):
            write(chunk)
        announce("🎲 orientace v mlze: 1d20+2 → [12] +2 = 14")
        messages.append({"role": "assistant",
                         "content": [{"type": "text", "text": "Stojíš na rozcestí."}]})


app = gui.AdventureWindow()
app.geometry("900x700")
app.update()

# --- the setup screen ---
check("it opens on the setup screen", app.setup_screen.winfo_ismapped())
check("every preset has a button", len(world.PRESETS) >= 6, len(world.PRESETS))
app.apply_preset("Vesmírná stanice")
app.update()
check("a preset fills the world box", "Kalypso" in app.world_box.get("1.0", "end"))
check("a preset sets the genre", app.genre.get() == "Sci-fi", app.genre.get())

app.player_count.set(2)
app.update()
check("two players means two character rows", len(app.character_rows) == 2)
app.character_rows[0][0].insert(0, "Marek")
app.character_rows[0][1].insert(0, "zloděj")
app.world_box.delete("1.0", "end")
app.world_box.insert("1.0", "Ostrov z ledu a kostí.")
app.genre.set("Fantasy")
app.update()

settings = app.collect_settings()
check("settings are a record", isinstance(settings, world.Settings), type(settings))
check("settings pick up the world", settings.world == "Ostrov z ledu a kostí.", settings.world)
check("settings pick up the genre", settings.genre is world.Genre.FANTASY, settings.genre)
check("settings pick up the character",
      settings.characters[0] == world.Character("Marek", "zloděj"), settings.characters)
check("the empty second row stays empty", not settings.characters[1].described)

# The dropdowns are built straight from the enums, so no list can drift out of sync.
check("the genre dropdown offers every genre",
      world.Genre.labels() == ["Realistický", "Fantasy", "Sci-fi", "Mysteriózní horor"],
      world.Genre.labels())

# A preset describes a world, not a party -- what the player typed has to survive it.
app.apply_preset("Temné podzemí")
app.update()
after_preset = app.collect_settings()
check("a preset keeps the characters already typed",
      after_preset.characters[0] == world.Character("Marek", "zloděj"), after_preset.characters)
check("a preset keeps the player count", after_preset.players == 2, after_preset.players)
check("a preset does change the world", "klášterem" in after_preset.world, after_preset.world[:40])
check("a preset does change the genre", after_preset.genre is world.Genre.HORROR)

# Put the test's own world back.
app.world_box.delete("1.0", "end")
app.world_box.insert("1.0", "Ostrov z ledu a kostí.")
app.genre.set("Fantasy")
app.update()
settings = app.collect_settings()

# --- one turn through the fake engine ---
app.engine = FakeEngine
app.settings = settings
brief = app.brief()
check("the brief carries the world", "Ostrov z ledu a kostí." in brief)
check("the brief carries the .md rules", "DALSI PRAVIDLA" in brief)

app.system = "system prompt for the test"
app.client = object()
app.messages = [{"role": "user", "content": world.first_message(settings)}]
app.show_game()
app.run_narrator()
wait_for_turn(app)
check("the engine was called once", len(FakeEngine.calls) == 1, len(FakeEngine.calls))
check("the engine got the system prompt",
      FakeEngine.calls[0]["system"] == "system prompt for the test")

story = app.story.get("1.0", "end")
check("the narration is in the window", "rozcestí" in story)
check("markdown is rendered, not shown", "**" not in story, story[:120])
check("the roll is in the window", "🎲" in story)
check("bold really is tagged",
      "rozcestí" in "".join(app.story.get(*span) for span in
                            zip(app.story.tag_ranges("bold")[::2],
                                app.story.tag_ranges("bold")[1::2])))

# --- the player sends something ---
app.entry.config(state="normal")
app.entry.insert(0, "Jdu doleva")
app.send()
wait_for_turn(app)
check("the player's action shows up", "▸ Jdu doleva" in app.story.get("1.0", "end"))
check("the action reached the engine",
      FakeEngine.calls[-1]["messages"][-1]["content"] == "Jdu doleva")

# --- saving and loading ---
app.save_game()
app.update()
check("the save file was written", os.path.exists(storage.SAVE_PATH))
saved_messages = list(app.messages)

written = json.load(open(storage.SAVE_PATH, encoding="utf-8"))
check("enums are stored by key, not as objects",
      written["settings"]["genre"] == "fantasy", written["settings"]["genre"])
check("characters are stored as plain dicts",
      written["settings"]["characters"][0] == {"name": "Marek", "description": "zloděj"},
      written["settings"]["characters"])

app.messages = []
app.clear_story()
app.load_game()
app.update()
check("loading restores the transcript", len(app.messages) == len(saved_messages),
      (len(app.messages), len(saved_messages)))
check("loading redraws the story", "rozcestí" in app.story.get("1.0", "end"))
check("loading restores the settings", app.settings.world == "Ostrov z ledu a kostí.")
check("loading restores the genre", app.settings.genre is world.Genre.FANTASY, app.settings.genre)
check("loading switches to the game screen", app.game_screen.winfo_ismapped())

# A hand-edited or truncated save must say so, not half-load a game.
good_settings = app.settings
broken = dict(written)
broken["settings"] = dict(written["settings"], genre="sciffi")
json.dump(broken, open(storage.SAVE_PATH, "w", encoding="utf-8"))
errors = []
gui.messagebox.showerror = lambda title, text: errors.append(text)
app.load_game()
app.update()
check("a corrupt save is reported", errors and "poškozená" in errors[0], errors)
check("a corrupt save leaves the old settings alone", app.settings == good_settings)
gui.messagebox.showerror = Silent.showerror
json.dump(written, open(storage.SAVE_PATH, "w", encoding="utf-8"))


# --- a failing engine must not take the window down ---
class BrokenEngine:
    @staticmethod
    def narrator_turn(client, messages, costs, write, announce, system=None):
        raise RuntimeError("spojení spadlo")


app.engine = BrokenEngine
app.entry.config(state="normal")
app.entry.delete(0, "end")
app.entry.insert(0, "Zkusím to znovu")
app.send()
wait_for_turn(app)
check("the error is shown to the player", "spojení spadlo" in app.story.get("1.0", "end"))
check("the failed action was taken back", app.messages[-1]["role"] != "user",
      app.messages[-1]["role"])
check("the window is still alive", app.winfo_exists())
check("input is enabled again", str(app.entry.cget("state")) == "normal")

app.destroy()
finish()
