"""Markdown arriving in chunks: nothing may leak, nothing may be lost.

The hard part is not the markdown itself but the fact that a marker can be split
across two network chunks, so every case is also run with random chunk sizes.
"""

import random

from harness import check, finish

from game.markdown_stream import Formatter


def render(text, size=None):
    """Runs text through the formatter in chunks (random-sized unless given)."""
    formatter = Formatter()
    spans = []
    i = 0
    while i < len(text):
        step = size or random.randint(1, 6)
        spans += formatter.feed(text[i:i + step])
        i += step
    return spans + formatter.flush()


def plain(spans):
    return "".join(text for text, _ in spans)


def styled(spans, style):
    return [text for text, styles in spans if style in styles]


# --- bold, italic, code ---
spans = render("Stojíš ve **Vrbnu** za *deště* a čteš `--help`.", size=1)
check("markers are gone", not any(m in plain(spans) for m in ("**", "*", "`")), plain(spans))
check("text is intact", plain(spans) == "Stojíš ve Vrbnu za deště a čteš --help.", plain(spans))
check("bold is marked", styled(spans, "bold") == ["Vrbnu"], styled(spans, "bold"))
check("italic is marked", styled(spans, "italic") == ["deště"], styled(spans, "italic"))
check("code is marked", styled(spans, "code") == ["--help"], styled(spans, "code"))

# --- headings, quotes, dividers ---
spans = render("## Kde jsme\n\n> „Zamkni to.\"\n\nVrbno, večer.\n\n---\n\nDalší scéna.\n")
check("heading loses its hashes", "#" not in plain(spans), plain(spans))
check("heading is marked", "Kde jsme" in "".join(styled(spans, "heading")))
check("quote loses its angle bracket", ">" not in plain(spans), plain(spans))
check("quote is marked", "Zamkni to." in "".join(styled(spans, "quote")))
check("divider became a rule", any("─" in text for text, _ in spans))
check("text after the divider survives", "Další scéna." in plain(spans))

# --- fenced code block ---
fenced = "Na displeji:\n\n```\nČekání na volbu\nzbývá 40 s\n```\n\nA dost.\n"
spans = render(fenced)
check("fences are not shown", "`" not in plain(spans), plain(spans))
check("block content is code", "Čekání na volbu" in "".join(styled(spans, "code")))
check("text around the block stays plain", "A dost." in plain(spans))

# --- things that only look like markdown ---
check("underscores are left alone",
      plain(render("Cesta_k_mlýnu je rozbitá.")) == "Cesta_k_mlýnu je rozbitá.")
check("a lone asterisk gets through",
      plain(render("Hvězdička * uprostřed věty.")) == "Hvězdička * uprostřed věty.")

# --- resilience to chunking ---
sample = ("## Scéna\n\nStojíš u **brány**. Vítr *sténá*, `log` mlčí.\n\n> Ticho.\n\n---\n\n"
          "Před tebou **tři** cesty a jeden *starý* muž.\n")
expected = sample
for marker in ("```", "**", "*", "## ", "> "):
    expected = expected.replace(marker, "")
expected = expected.replace("`", "")

for attempt in range(300):
    spans = render(sample)
    rebuilt = plain(spans).replace("─" * 48, "---")
    if rebuilt != expected:
        check("nothing is lost or added", False, (attempt, repr(rebuilt[:120])))
        break
    if styled(spans, "bold") != ["brány", "tři"]:
        check("styles survive chunking", False, (attempt, styled(spans, "bold")))
        break
else:
    check("nothing is lost or added (300 chunkings)", True)

for attempt in range(200):
    if "`" in plain(render(fenced)):
        check("a split fence never flashes a backtick", False, attempt)
        break
else:
    check("a split fence never flashes a backtick (200 chunkings)", True)

# --- an unfinished marker is held back until it is settled ---
formatter = Formatter()
first = formatter.feed("Stojíš ve **Vrb")
check("unfinished bold is held back", "Vrb" not in plain(first), plain(first))
second = formatter.feed("nu** za deště.")
check("it appears once complete", "Vrbnu" in plain(second), plain(second))
check("and it is bold", "Vrbnu" in styled(second, "bold"), styled(second, "bold"))

# --- an unclosed code block must not bleed into the next turn ---
formatter = Formatter()
formatter.feed("```\nnedokončené\n")
formatter.flush()
spans = formatter.feed("Úplně běžná věta.\n") + formatter.flush()
check("flush closes an open code block", styled(spans, "code") == [], spans)

finish()
