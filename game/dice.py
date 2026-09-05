"""Dice rolling. The program rolls, never the model.

Both engines share this: whatever the narrator asks for, the number comes from
random.randint() here, so the story cannot bend a roll it did not like.

Czech notation uses 'k' where English uses 'd' (k20 = d20), so both are accepted.
"""

import random
import re

NOTATION = re.compile(r"^\s*(\d*)\s*[dk]\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.IGNORECASE)
ALLOWED_SIDES = {2, 4, 6, 8, 10, 12, 20, 100}
MAX_DICE = 20


def roll(notation):
    """Parses notation such as '2d6+3' and rolls it.

    Returns (individual rolls, bonus, total). Raises ValueError on anything the
    narrator may have made up, so the caller can ask it for a proper notation.
    """
    match = NOTATION.match(notation)
    if not match:
        raise ValueError(f"nesrozumitelny zapis hodu: {notation!r}")

    count = int(match.group(1) or 1)
    sides = int(match.group(2))
    bonus = 0
    if match.group(3):
        bonus = int(match.group(4)) * (-1 if match.group(3) == "-" else 1)

    if not 1 <= count <= MAX_DICE:
        raise ValueError(f"pocet kostek musi byt 1 az {MAX_DICE}")
    if sides not in ALLOWED_SIDES:
        raise ValueError(f"neexistujici kostka d{sides}")

    rolls = [random.randint(1, sides) for _ in range(count)]
    return rolls, bonus, sum(rolls) + bonus


def describe(notation, reason, rolls, bonus, total):
    """The line shown to the player, e.g. '🎲 útok mečem: 1d20+3 → [14] +3 = 17'."""
    bonus_part = f" {bonus:+d}" if bonus else ""
    return f"🎲 {reason}: {notation} → {rolls}{bonus_part} = {total}"
