"""Narrator powered by the Claude API, paid for with API credit.

The model asks for a roll by calling the hod_kostkou tool; the program rolls and
sends the real number back, so the model never decides an outcome by itself.

engine_claude_code.py offers the same narrator_turn() interface but spends a Claude
subscription instead. The window talks to whichever is available and cannot tell
the difference.

The anthropic package is optional: someone playing on a subscription never needs it,
so a missing one only closes this path instead of stopping the game from starting.
Everything that touches the package goes through create_client() and describe_error().
"""

import sys

from . import dice, prompts

try:
    import anthropic
except ImportError:
    anthropic = None

AVAILABLE = anthropic is not None
MISSING_PACKAGE = "Chybi balicek anthropic. Nainstaluj ho:  pip install anthropic"

# A Czech console runs in cp1250, which cannot encode emoji or arrows -- without
# this the narration would die on the first dice symbol.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

MODEL = "claude-opus-5"
MAX_TOKENS = 4000
EFFORT = "medium"           # low = faster and cheaper, high = more considered

# Model prices in dollars per million tokens (Claude Opus 5).
PRICE_INPUT = 5.00
PRICE_OUTPUT = 25.00
PRICE_CACHE_WRITE = 6.25    # 1.25x input
PRICE_CACHE_READ = 0.50     # 0.1x input

# How the narrator asks for a roll on this path: by calling the tool below.
DICE_RULES_TOOL = """
- O hod si rekni zavolanim nastroje hod_kostkou. Pred hodem strucne rekni, o co se hazi,
  po hodu popis, co se stalo. Nikdy nepis vysledek kostek sam od sebe."""

DICE_TOOL = {
    "name": "hod_kostkou",
    "description": (
        "Hodi kostkami a vrati skutecne nahodny vysledek. Pouzij vzdy, kdyz vysledek akce "
        "zavisi na nahode -- utok, plizeni, presvedcovani, hledani, past, riskantni manevr. "
        "Nikdy vysledek nevymysli sam."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "zapis": {
                "type": "string",
                "description": "Zapis hodu, napriklad '1d20', '1d20+3', '2d6', '3d8-1'.",
            },
            "duvod": {
                "type": "string",
                "description": "Kratce o co se hazi, napriklad 'utok mecem na goblina'.",
            },
        },
        "required": ["zapis", "duvod"],
    },
}


def build_system_prompt(brief=""):
    """Assembles the system prompt with the dice rules last.

    The order is not cosmetic: when the world brief was appended after the dice
    rules, the narrator started making up roll results instead of asking for them.
    """
    return prompts.NARRATOR_BASE + brief + prompts.DICE_RULES + DICE_RULES_TOOL


SYSTEM_PROMPT = build_system_prompt()


class Costs:
    """Adds up tokens and estimates what the game has cost."""

    def __init__(self):
        self.input = self.output = self.cache_write = self.cache_read = 0

    def add(self, usage):
        self.input += usage.input_tokens
        self.output += usage.output_tokens
        self.cache_write += usage.cache_creation_input_tokens or 0
        self.cache_read += usage.cache_read_input_tokens or 0

    @property
    def dollars(self):
        return (
            self.input * PRICE_INPUT
            + self.output * PRICE_OUTPUT
            + self.cache_write * PRICE_CACHE_WRITE
            + self.cache_read * PRICE_CACHE_READ
        ) / 1_000_000

    def summary(self):
        return (
            f"tokeny: {self.input} vstup / {self.output} vystup / "
            f"{self.cache_read} z cache  |  odhad ceny: ${self.dollars:.3f}"
        )

    def status_text(self):
        """Short text for the window's status line."""
        return f"${self.dollars:.3f}"


def create_client():
    """A client for the API, or a clear error when the package is not installed."""
    if not AVAILABLE:
        raise RuntimeError(MISSING_PACKAGE)
    return anthropic.Anthropic()


def describe_error(error):
    """Turns an exception from a turn into one line for the player.

    The API's own errors carry a status code worth showing; everything else, and
    everything at all when the package is missing, falls back to its own message.
    """
    if AVAILABLE:
        if isinstance(error, anthropic.APIStatusError):
            return f"Chyba API {error.status_code}: {error.message}"
        if isinstance(error, anthropic.APIConnectionError):
            return "Výpadek spojení. Zkus to znovu."
    return f"Neočekávaná chyba: {error}"


def write_to_console(text):
    """Default way of showing narration -- straight into the terminal."""
    print(text, end="", flush=True)


def announce_to_console(text):
    """Default way of showing a dice roll or a message from the program."""
    print(text)


def _roll_for_tool(block, announce=announce_to_console):
    """Runs one requested roll and returns the tool_result for the model."""
    notation = str(block.input.get("zapis", ""))
    reason = str(block.input.get("duvod", "hod"))
    try:
        rolls, bonus, total = dice.roll(notation)
    except ValueError as error:
        announce(f"[kostka] {error}")
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Chyba: {error}. Pouzij zapis jako '1d20+3'.",
            "is_error": True,
        }

    announce(dice.describe(notation, reason, rolls, bonus, total))
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": (
            f"Hod {notation} ({reason}): jednotlive kostky {rolls}, bonus {bonus:+d}, "
            f"celkovy vysledek {total}."
        ),
    }


def narrator_turn(client, messages, costs, write=write_to_console,
                  announce=announce_to_console, system=None):
    """Lets the model narrate until it asks for dice, rolls them, and carries on.

    `write` receives narration in chunks as it arrives from the network; `announce`
    receives messages from the program (rolls, errors). The console and the window
    differ in nothing but these two callbacks.
    """
    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system or SYSTEM_PROMPT,
            tools=[DICE_TOOL],
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                write(chunk)
            response = stream.get_final_message()

        write("\n")
        costs.add(response.usage)
        messages.append(
            {
                "role": "assistant",
                "content": [b.model_dump(exclude_none=True) for b in response.content],
            }
        )

        if response.stop_reason == "refusal":
            announce("[Vypravec tuto scenu odmitl dovypravet. Zkus ji nasmerovat jinam.]")
            return
        if response.stop_reason != "tool_use":
            return

        results = [_roll_for_tool(b, announce) for b in response.content if b.type == "tool_use"]
        messages.append({"role": "user", "content": results})
