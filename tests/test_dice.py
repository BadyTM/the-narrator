"""Dice notation: what the narrator may ask for and what has to be refused."""

from harness import check, finish

from game import dice

rolls, bonus, total = dice.roll("2d6+3")
check("2d6+3 rolls two dice", len(rolls) == 2, rolls)
check("2d6+3 keeps the bonus", bonus == 3, bonus)
check("2d6+3 adds up", total == sum(rolls) + 3, (rolls, total))
check("2d6 stays in range", all(1 <= r <= 6 for r in rolls), rolls)

check("a bare d20 means one die", len(dice.roll("d20")[0]) == 1)
check("Czech k20 works too", 1 <= dice.roll("k20")[2] <= 20)
check("a negative bonus is kept", dice.roll("1d20-2")[1] == -2)
check("spaces do not matter", dice.roll("  3 d 8 + 1 ")[1] == 1)

for bad in ("2 kostky", "1d7", "0d6", "21d6", "", "d20+", "hodně"):
    try:
        dice.roll(bad)
        check(f"{bad!r} is refused", False, "no error raised")
    except ValueError:
        check(f"{bad!r} is refused", True)

# A d20 has to actually produce different numbers -- a frozen die would be invisible
# in play but would quietly kill every roll in the game.
seen = {dice.roll("1d20")[2] for _ in range(200)}
check("a d20 gives varied results", len(seen) > 10, len(seen))

line = dice.describe("1d20+2", "plížení", [14], 2, 16)
check("the roll line names the reason", "plížení" in line, line)
check("the roll line shows the total", line.endswith("= 16"), line)
check("no bonus, no plus sign", "+" not in dice.describe("1d20", "útok", [7], 0, 7))

finish()
