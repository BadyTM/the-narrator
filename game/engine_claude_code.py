"""Narrator powered by Claude Code, spending a subscription instead of API credit.

Instead of calling the API we start `claude` as a subprocess in non-interactive mode
and talk to it in JSON lines -- one process, in both directions, for the whole game.

The model does not roll. It asks for a roll with a marker written into the text:

    [HOD: 1d20+3 | utok mecem]

The program catches the marker before it reaches the screen, rolls a real die and
sends the result back as the next message, so the outcome is never the model's.

The interface matches engine_api.py on purpose: the window cannot tell them apart.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading

from . import dice, prompts

# The marker the narrator uses to ask for a roll -- something ordinary prose never contains.
ROLL_MARKER = re.compile(r"\[HOD:\s*([^|\]]+?)\s*(?:\|\s*([^\]]*?))?\s*\]", re.IGNORECASE)

# Windows cuts a command line off at 8191 characters. Everything the system prompt
# holds is passed as one argument, so it has to stay well under that; the world brief
# and the house rules travel through the pipe instead (see ClaudeCodeNarrator.briefing).
MAX_COMMAND_LENGTH = 7500

MAX_RECAP_CHARS = 12000     # how much of the story we replay after loading a game
MAX_ROLL_ROUNDS = 6         # guard against the narrator chaining rolls forever

DICE_RULES_MARKER = """

=== NEJDULEZITEJSI PRAVIDLO CELE HRY ===

Kostky hazi program, ne ty. Ty vysledek hodu NIKDY neznas dopredu a NIKDY si ho nevymyslis.

Kdyz ma o necem rozhodnout nahoda, napises PRESNE tuhle znacku a OKAMZITE prestanes psat:

    [HOD: 1d20+3 | utok mecem]

Pak uz nenapises ani slovo. Skoncis uprostred sceny. Vysledek ti prijde v dalsi zprave
a teprve pak dovypravis, co se stalo.

ZAKAZANO -- takhle to NIKDY nedelej:
    "Hod na utok: k20 -> 17 + 5 = 22, zasah!"
    "Hodis si... 14. To staci."
    "🎲 Utok: 18"
Zadna cisla hodu, zadne sipky s vysledkem, zadny symbol kostky. To vsechno pise program.

SPRAVNE:
    "Goblin se zubi a mava tesakem. Vyrazis po nem.
    [HOD: 1d20+5 | utok mecem na goblina]"
    ...a tady prestanes psat a cekas.

Pokud jsi napsal znacku, tvoje odpoved timhle konci. Zadne "uvidime", zadne pokracovani.
V jedne odpovedi nejvyse dve znacky.

Kolik hodu za tah: nejvyse dva CELKEM za jeden tah hrace, ne dva pokazde. Kdyz uz mas
vysledky, tah dopis do konce a nech hrace jednat -- i kdyby zbyvalo neco nejisteho.
To rozhodni vypravenim. Kazdy dalsi hod znamena pro hrace pul minuty cekani u prazdneho
okna, takze retezit hody za sebou je horsi nez rozhodnout to sam.
Kdyz potrebujes dva hody, rekni si o oba naraz v jedne odpovedi."""

# Claude Code normally introduces itself as a coding assistant; without this it starts
# talking about files and projects in the middle of a fantasy tavern.
NOT_AN_ASSISTANT = """

Nejsi programatorsky asistent a nemas k dispozici zadne nastroje. Nikdy nemluv o
souborech, projektech, repozitarich ani o "teto relaci" a nenabizej, ze si neco
prectes nebo ulozis. Vsechno, co ke hre potrebujes, je napsane vyse. Kdyz ti neco
chybi, vymysli si to a hraj dal."""

# The rule dissolves in a long conversation, so every turn carries a short reminder.
TURN_REMINDER = (
    "\n\n(Pripominka pravidel: o nejisty vysledek si rekni znackou [HOD: kostky | duvod] "
    "a hned za ni prestan psat. Nikdy nepis cisla hodu sam. Nejvyse dva hody za tento tah "
    "-- pak dopis scenu a nech me jednat.)"
)

# Claude Code's tools are useless for storytelling and would only stop to ask for
# permissions. The narrator gets by on text alone.
DISABLED_TOOLS = [
    "Bash", "Edit", "Write", "Read", "Glob", "Grep",
    "WebSearch", "WebFetch", "Task", "NotebookEdit", "TodoWrite",
]


def build_system_prompt(brief=""):
    """Assembles the system prompt with the dice rules last.

    The order is not cosmetic: when the world brief was appended after the dice
    rules, the narrator ignored the dice and made the results up.
    """
    return (prompts.NARRATOR_BASE + brief + NOT_AN_ASSISTANT
            + prompts.DICE_RULES + DICE_RULES_MARKER)


SYSTEM_PROMPT = build_system_prompt()


def build_recap(messages):
    """Turns a saved transcript into the text that resumes an interrupted game."""
    parts = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "user" and isinstance(content, str):
            parts.append(f"HRAC: {content}")
        elif message.get("role") == "assistant" and isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    parts.append(f"TY (vypravec): {block['text']}")
    story = "\n\n".join(parts).strip()
    if not story:
        return ""
    if len(story) > MAX_RECAP_CHARS:
        story = "…(starsi cast deje vynechana)…\n\n" + story[-MAX_RECAP_CHARS:]

    return (
        "POKRACUJEME V ROZEHRANE HRE. Tohle se doposud stalo -- je to tvoje vlastni "
        "drivejsi vypraveni a hracovy akce:\n\n<<<\n" + story + "\n>>>\n\n"
        "Navaz presne tam, kde to skoncilo. Nepredstavuj svet znovu, nevitej hrace, "
        "neshrnuj, co uz vis, a na nic se neptej. Ted hrac dela tohle:\n\n"
    )


def session_dir():
    """An empty but STABLE folder for Claude Code to run in.

    Two things at once: inside the project folder it would pull in the repository
    context and the narrator would start sounding like a coding assistant, while a
    fresh temp folder every time would lose its earlier sessions.
    """
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = os.path.join(base, "the-narrator", "sessions")
    os.makedirs(path, exist_ok=True)
    return path


def find_claude():
    """Path to the Claude Code executable, or None."""
    for name in ("claude.cmd", "claude.exe", "claude"):
        found = shutil.which(name)
        if found:
            return found
    npm_default = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
    return npm_default if os.path.exists(npm_default) else None


class SubscriptionCosts:
    """A subscription is not billed in dollars, so we track turns and tokens."""

    def __init__(self):
        self.turns = 0
        self.input = self.output = self.cache_read = 0

    def add(self, usage):
        self.turns += 1
        self.input += usage.get("input_tokens", 0)
        self.output += usage.get("output_tokens", 0)
        self.cache_read += usage.get("cache_read_input_tokens", 0)

    def status_text(self):
        if self.turns == 1:
            word = "tah"
        elif 2 <= self.turns <= 4:
            word = "tahy"
        else:
            word = "tahů"
        return f"{self.turns} {word} · {self.output} tokenů"

    def summary(self):
        return (
            f"tahy: {self.turns}  |  tokeny: {self.input} vstup / {self.output} vystup / "
            f"{self.cache_read} z cache  |  ucteno z predplatneho"
        )


class MarkerFilter:
    """Passes text through to the screen but keeps roll markers off it.

    Text arrives in small chunks, so a marker can be split across several of them.
    Everything from a '[' is therefore held back until the ']' arrives -- only then
    can we tell a roll marker from an ordinary bracket.
    """

    def __init__(self):
        self.held = ""
        self.rolls = []

    def feed(self, chunk):
        """Returns the text that is safe to show now."""
        self.held += chunk
        showable = ""

        while True:
            if "[" not in self.held:
                showable += self.held
                self.held = ""
                break

            before, rest = self.held.split("[", 1)
            showable += before
            if "]" not in rest:
                self.held = "[" + rest          # wait for the closing bracket
                break

            inside, after = rest.split("]", 1)
            bracketed = f"[{inside}]"
            match = ROLL_MARKER.fullmatch(bracketed)
            if match:
                self.rolls.append((match.group(1).strip(), (match.group(2) or "hod").strip()))
            else:
                showable += bracketed           # an ordinary bracket, let it through
            self.held = after

        return showable

    def flush(self):
        """At the end of a reply, releases whatever is still held back."""
        rest, self.held = self.held, ""
        return rest


class ClaudeCodeNarrator:
    """Holds a running `claude` process and sends the player's turns to it."""

    def __init__(self, session_id=None, executable=None, system=None, recap=None, briefing=""):
        """`recap` is the story so far, sent ahead of the first message.

        Resuming used to be done with --resume, but that never restored the earlier
        narration: Claude Code ignores the --session-id we ask for and quietly starts
        a fresh session, leaving the narrator with no idea what had happened. We
        therefore replay our own saved story rather than rely on its internals.

        `briefing` is the world settings and the house rules. It travels through the
        pipe in the first message rather than in the system prompt, because that one
        is passed as a command-line argument and would blow past the Windows limit.
        """
        self.briefing = briefing
        self.recap = recap
        self.system = system or SYSTEM_PROMPT
        self.workdir = session_dir()
        self.executable = executable or find_claude()
        if not self.executable:
            raise RuntimeError(
                "Nenasel jsem Claude Code. Nainstaluj ho pres:  npm install -g @anthropic-ai/claude-code"
            )
        # The real session id is unknown until the first reply arrives.
        self.session_id = session_id
        self.process = None
        self.stderr_lines = []

    def command(self):
        """The command line that starts Claude Code."""
        return [
            self.executable, "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--system-prompt", self.system,
            "--disallowedTools", *DISABLED_TOOLS,
        ]

    def start(self):
        command = self.command()
        # Over the limit Windows fails with "The command line is too long." and the
        # game dies before saying anything -- better to explain what actually happened.
        length = sum(len(part) + 3 for part in command)
        if length > MAX_COMMAND_LENGTH:
            raise RuntimeError(
                f"Systemovy prompt je moc dlouhy pro prikazovou radku ({length} znaku, "
                "strop je 8191). Zkrat pravidla vypravece v engine_claude_code.py."
            )
        # We force no session id -- Claude Code assigns its own anyway and we read it
        # back from the first reply (handy in a save file when debugging).
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=self.workdir,
        )
        threading.Thread(target=self._collect_stderr, daemon=True).start()
        return self

    def _collect_stderr(self):
        for line in self.process.stderr:
            self.stderr_lines.append(line)

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def send(self, text):
        if not self.is_running():
            raise RuntimeError(self._crash_message())
        message = {"type": "user", "message": {"role": "user", "content": text}}
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _crash_message(self):
        details = "".join(self.stderr_lines).strip()
        return f"Claude Code skoncil.\n{details}" if details else "Claude Code nečekaně skončil."

    def read_reply(self, write, costs):
        """Reads one reply up to the 'result' event. Returns the rolls it asked for."""
        marker_filter = MarkerFilter()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(self._crash_message())
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # The real session id only shows up in the stream; we overwrite ours with
            # it so a saved game records the session it actually came from.
            if event.get("session_id"):
                self.session_id = event["session_id"]

            kind = event.get("type")
            if kind == "stream_event":
                delta = event.get("event", {}).get("delta", {})
                if delta.get("type") == "text_delta":
                    write(marker_filter.feed(delta["text"]))
            elif kind == "result":
                write(marker_filter.flush())
                costs.add(event.get("usage", {}))
                if event.get("is_error"):
                    raise RuntimeError(event.get("result") or "Claude Code vrátil chybu.")
                return marker_filter.rolls

    def stop(self):
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
        # The working folder stays: the Claude Code session is tied to it.

    def take_preamble(self):
        """The briefing and recap, each sent only once, ahead of the player's action."""
        preamble = ""
        if self.briefing:
            preamble = self.briefing + "\n\n"
            self.briefing = ""
        if self.recap:
            preamble += self.recap
            self.recap = None
        return preamble


def _write_to_console(text):
    print(text, end="", flush=True)


def _announce_to_console(text):
    print(text)


def narrator_turn(narrator, messages, costs, write=_write_to_console,
                  announce=_announce_to_console, system=None):
    """Same interface as engine_api.narrator_turn, but driven by Claude Code.

    `messages` is now only a transcript for the window and the save file -- the
    conversation itself lives in the Claude Code session.

    `system` is ignored here: Claude Code was given the prompt when it started.
    """
    last = messages[-1] if messages else None
    action = (last["content"] if last and last["role"] == "user"
              and isinstance(last["content"], str) else "Pokracuj.")

    narrator.send(narrator.take_preamble() + action + TURN_REMINDER)

    # The narration is also kept in `messages` so a loaded game can be redrawn.
    written = []

    def write_and_remember(chunk):
        written.append(chunk)
        write(chunk)

    def remember_turn():
        text = "".join(written).strip()
        if text:
            messages.append({"role": "assistant", "content": [{"type": "text", "text": text}]})

    for _ in range(MAX_ROLL_ROUNDS):
        rolls = narrator.read_reply(write_and_remember, costs)
        write("\n")
        if not rolls:
            remember_turn()
            return

        results = []
        for notation, reason in rolls:
            try:
                dice_rolled, bonus, total = dice.roll(notation)
            except ValueError as error:
                announce(f"[kostka] {error}")
                results.append(f"Hod {notation} nelze provest ({error}). Pouzij tvar jako 1d20+3.")
                continue
            announce(dice.describe(notation, reason, dice_rolled, bonus, total))
            results.append(f"Hod {notation} ({reason}): kostky {dice_rolled}, "
                           f"bonus {bonus:+d}, vysledek {total}.")

        narrator.send("Vysledky hodu:\n" + "\n".join(results) + "\nPokracuj ve vypraveni.")

    remember_turn()
    announce("[Vypravec si rekl o prilis mnoho hodu za sebou, tah ukoncen.]")
