"""Does the story follow the player's intent when text keeps arriving?

The rule: follow to the bottom while the player is at the bottom, stop following the
moment they scroll up to read, and start again when they come back down.

The bug this guards against: the window used to measure the position before every
insert, and during fast streaming yview() still reports the old one. A single stale
reading unstuck the view for the rest of the turn -- after three turns the player was
looking at the beginning of the story while the narrator wrote at the end.
"""

import os
import tempfile
import time

from harness import check, finish

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

from game import gui, storage

gui.BACKEND = "api"
storage.SAVE_PATH = os.path.join(tempfile.mkdtemp(), "save.json")

SCENE = ("Mlha sedí na silnici jako mokrý hadr a nikam se nehne. "
         "Za sklem se pohne stín, pak druhý, a pak už se nedá počítat.\n\n") * 12


def scroll_to(window, position):
    """Scrolls the way a player does -- with the wheel, not by calling yview()."""
    window.story.yview_moveto(position)
    window.story.event_generate("<MouseWheel>", delta=-120 if position > 0.5 else 120)
    window.update()


app = gui.AdventureWindow()
app.geometry("900x600")
app.show_game()
app.update()

# --- following along ---
for i in range(40):
    app.write(f"Řádek {i}: {SCENE[:80]}\n")
app.update()
check("after filling up we are at the bottom", app.is_at_bottom(), app.story.yview())

# --- fast streaming must not unstick the view ---
for i in range(400):
    app.write(f"slovo{i} ")        # deliberately no update() in between
app.update()
check("fast streaming keeps us at the bottom", app.is_at_bottom(), app.story.yview())
check("and the window still means to follow", app.stick_to_bottom)

# --- a player who scrolls up is left alone ---
scroll_to(app, 0.0)
before = app.story.yview()
check("scrolling up unsticks the view", not app.stick_to_bottom, before)
for i in range(30):
    app.write(f"další slovo {i} ")
app.update()
check("incoming text does not yank the view", abs(app.story.yview()[0] - before[0]) < 0.02,
      (before, app.story.yview()))

# --- the player's own action always brings them back ---
app.write("\n▸ Jdu doleva\n\n", "player", force_bottom=True)
app.update()
check("your own action scrolls you down", app.is_at_bottom(), app.story.yview())

# --- coming back down starts the following again ---
scroll_to(app, 0.0)
check("we are up again", not app.stick_to_bottom)
scroll_to(app, 1.0)
check("returning to the end sticks again", app.stick_to_bottom, app.story.yview())
app.write("A příběh pokračuje.\n")
app.update()
check("and text follows once more", app.is_at_bottom(), app.story.yview())


# --- the same through the real path: background thread, queue, dice announcement ---
class StreamingEngine:
    @staticmethod
    def narrator_turn(client, messages, costs, write, announce, system=None):
        for i in range(0, len(SCENE), 25):
            write(SCENE[i:i + 25])
            time.sleep(0.002)
        announce("🎲 plížení chodbou: 1d20+2 → [11] +2 = 13")
        for i in range(0, len(SCENE), 25):
            write(SCENE[i:i + 25])
            time.sleep(0.002)
        messages.append({"role": "assistant", "content": [{"type": "text", "text": SCENE}]})


app.engine = StreamingEngine
app.client = object()
app.system = None
app.messages = []

for turn in range(3):
    app.entry.config(state="normal")
    app.entry.delete(0, "end")
    app.entry.insert(0, f"Akce číslo {turn}")
    app.send()
    deadline = time.time() + 15
    while app.busy and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    app.update()
    check(f"turn {turn + 1} ends at the bottom", app.is_at_bottom(),
          f"yview={app.story.yview()} stick={app.stick_to_bottom}")

app.save_game()          # writes a notice with a very long path into the story
app.update()
check("saving leaves the view at the bottom", app.is_at_bottom(),
      f"yview={app.story.yview()} stick={app.stick_to_bottom}")

app.destroy()
finish()
