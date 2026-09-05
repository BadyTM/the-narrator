"""The Claude Code engine without launching Claude Code.

Covered here: pulling roll markers out of streamed text, the command line staying
under the Windows limit, and the briefing being sent exactly once.
"""

from harness import check, finish

from game import engine_claude_code as engine
from game import rules_loader, world

# --- markers split across chunks ---
def collect(chunks):
    """Feeds chunks through the filter and returns (visible text, rolls asked for)."""
    marker_filter = engine.MarkerFilter()
    shown = "".join(marker_filter.feed(chunk) for chunk in chunks)
    return shown + marker_filter.flush(), marker_filter.rolls


shown, rolls = collect(["Vyrazíš po něm.\n[HOD: 1d20+5 | útok mečem]"])
check("the marker never reaches the screen", "[HOD" not in shown, shown)
check("the roll is captured", rolls == [("1d20+5", "útok mečem")], rolls)

shown, rolls = collect(["Vyrazíš.\n[HOD: 1d2", "0+5 | útok", " mečem]"])
check("a marker split in three still works", rolls == [("1d20+5", "útok mečem")], rolls)
check("nothing leaks while it is split", "[" not in shown, shown)

shown, rolls = collect(["Na stole leží dopis [zapečetěný] a nůž."])
check("an ordinary bracket gets through", "[zapečetěný]" in shown, shown)
check("an ordinary bracket is not a roll", rolls == [], rolls)

shown, rolls = collect(["Dvojice: [HOD: 1d20 | Lukáš] a [HOD: 1d20 | Petr]"])
check("two markers in one reply are both caught", len(rolls) == 2, rolls)

shown, rolls = collect(["Bez důvodu: [HOD: 2d6]"])
check("a marker without a reason still rolls", rolls == [("2d6", "hod")], rolls)

marker_filter = engine.MarkerFilter()
streamed = marker_filter.feed("Nedokončená závorka [HOD: 1d20")
check("an unfinished marker is held back while streaming", "[HOD" not in streamed, streamed)
check("but it is not swallowed at the end", "[HOD: 1d20" in marker_filter.flush())

# --- system prompt and command line ---
system = engine.build_system_prompt()
check("the system prompt has no world brief", "ZADANI TETO HRY" not in system, len(system))
check("the dice rule comes last",
      system.rstrip().endswith("rekni si o oba naraz v jedne odpovedi."), system[-60:])
check("the narrator is told it is not an assistant", "Nejsi programatorsky asistent" in system)

long_world = "Praha 2026. " + "Další podrobnost o světě. " * 200
brief = world.build_brief(world.Settings(world=long_world)) + rules_loader.load()
check("this test really uses a long brief", len(brief) > 8191, len(brief))

narrator = engine.ClaudeCodeNarrator(system=system, briefing=brief, executable="C:\\claude.cmd")
length = sum(len(part) + 3 for part in narrator.command())
check("the command line stays under the Windows limit", length < engine.MAX_COMMAND_LENGTH, length)

# --- the briefing travels through the pipe, and only once ---
sent = []
narrator.send = sent.append
narrator.read_reply = lambda write, costs: []
messages = [{"role": "user", "content": "Zacni prvni scenou."}]
engine.narrator_turn(narrator, messages, engine.SubscriptionCosts(),
                     write=lambda _: None, announce=lambda _: None)
check("the first message carries the brief", "ZADANI TETO HRY" in sent[0], sent[0][:60])
check("the first message carries the .md rules", "DALSI PRAVIDLA" in sent[0])
check("the first message carries the player's action", "Zacni prvni scenou." in sent[0])
check("it also carries the rules reminder", "Pripominka pravidel" in sent[0])

sent.clear()
engine.narrator_turn(narrator, messages, engine.SubscriptionCosts(),
                     write=lambda _: None, announce=lambda _: None)
check("the second turn does not repeat the brief", "ZADANI TETO HRY" not in sent[0], sent[0][:60])

# --- an oversized prompt fails with an explanation, not a cryptic crash ---
try:
    engine.ClaudeCodeNarrator(system="x" * 9000, executable="C:\\claude.cmd").start()
    check("an oversized prompt is reported clearly", False, "no error raised")
except RuntimeError as error:
    check("an oversized prompt is reported clearly", "moc dlouhy" in str(error), error)

# --- resuming a saved game ---
recap = engine.build_recap([
    {"role": "user", "content": "Jdu do hospody U Kotvy."},
    {"role": "assistant", "content": [{"type": "text", "text": "Na stole leží červený dopis."}]},
])
check("the recap contains the player's action", "U Kotvy" in recap)
check("the recap contains the narration", "červený dopis" in recap)
check("the recap forbids starting over", "Nepredstavuj svet znovu" in recap)
check("an empty history has no recap", engine.build_recap([]) == "")

long_history = [{"role": "assistant", "content": [{"type": "text", "text": "x" * 30000}]}]
check("a long history is trimmed",
      len(engine.build_recap(long_history)) < engine.MAX_RECAP_CHARS + 1000,
      len(engine.build_recap(long_history)))

# --- the status line counts turns in Czech ---
costs = engine.SubscriptionCosts()
for expected in ("1 tah", "2 tahy", "3 tahy", "4 tahy", "5 tahů"):
    costs.add({"output_tokens": 10})
    check(f"status line says {expected!r}", costs.status_text().startswith(expected),
          costs.status_text())

finish()
