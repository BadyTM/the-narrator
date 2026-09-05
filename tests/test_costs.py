"""Counting what a game costs: the two billing models behind one interface.

The counter is not decoration. A rules change once made the narrator chain dice
rolls, and the turn count going from 5 to 24 for the same four turns is what made
that visible -- the prose read fine.
"""

from harness import check, finish

from game import engine_api
from game import engine_claude_code as cc


class Usage:
    """What the API reports back after a turn."""

    def __init__(self, input_tokens=0, output_tokens=0, cache_write=0, cache_read=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_write
        self.cache_read_input_tokens = cache_read


# --- paying with API credit ---
costs = engine_api.Costs()
check("a fresh game costs nothing", costs.dollars == 0, costs.dollars)
check("and says so", costs.status_text() == "$0.000", costs.status_text())

costs.add(Usage(input_tokens=1_000_000))
check("a million input tokens costs the input price", costs.dollars == engine_api.PRICE_INPUT,
      costs.dollars)

costs = engine_api.Costs()
costs.add(Usage(output_tokens=1_000_000))
check("output is priced separately", costs.dollars == engine_api.PRICE_OUTPUT, costs.dollars)

# The point of counting cache reads apart: they are a tenth of fresh input, and a game
# re-sends the whole story every turn, so lumping them in would overstate the price.
fresh, cached = engine_api.Costs(), engine_api.Costs()
fresh.add(Usage(input_tokens=100_000))
cached.add(Usage(cache_read=100_000))
check("a cache read costs a tenth of fresh input",
      round(fresh.dollars / cached.dollars, 6) == 10.0, (fresh.dollars, cached.dollars))
check("a cache write costs more than fresh input, not less",
      engine_api.PRICE_CACHE_WRITE > engine_api.PRICE_INPUT)

costs = engine_api.Costs()
costs.add(Usage(1200, 800, 0, 30000))
costs.add(Usage(1300, 900, 0, 34000))
check("turns add up", (costs.input, costs.output, costs.cache_read) == (2500, 1700, 64000),
      (costs.input, costs.output, costs.cache_read))
expected = (2500 * 5.00 + 1700 * 25.00 + 64000 * 0.50) / 1_000_000
check("the total is the sum of all four rates", abs(costs.dollars - expected) < 1e-9,
      (costs.dollars, expected))
check("the status line is short enough for the toolbar",
      costs.status_text().startswith("$") and len(costs.status_text()) <= 8,
      costs.status_text())
check("the summary names all three kinds of token",
      all(word in costs.summary() for word in ("vstup", "vystup", "cache")), costs.summary())

# --- paying with a subscription ---
subscription = cc.SubscriptionCosts()
check("no turns yet", subscription.turns == 0)

for _ in range(5):
    subscription.add({"input_tokens": 1200, "output_tokens": 1686,
                      "cache_read_input_tokens": 30000})
check("every reply counts as a turn", subscription.turns == 5, subscription.turns)
check("output adds up", subscription.output == 8430, subscription.output)
check("the status line shows turns and output",
      subscription.status_text() == "5 tahů · 8430 tokenů", subscription.status_text())
check("no dollar figure is invented for a subscription",
      "$" not in subscription.status_text() and "$" not in subscription.summary(),
      subscription.summary())

# A missing field must not take a turn down -- the stream does not always carry them.
sparse = cc.SubscriptionCosts()
sparse.add({})
check("a reply with no usage still counts", sparse.turns == 1, sparse.turns)
check("and leaves the tokens at zero", (sparse.input, sparse.output) == (0, 0))

# --- both are interchangeable as far as the window is concerned ---
for counter in (engine_api.Costs(), cc.SubscriptionCosts()):
    name = type(counter).__name__
    check(f"{name} offers add()", callable(getattr(counter, "add", None)))
    check(f"{name} offers status_text()", isinstance(counter.status_text(), str))
    check(f"{name} offers summary()", isinstance(counter.summary(), str))

finish()
