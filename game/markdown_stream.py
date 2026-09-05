"""Turns the narrator's markdown into styled spans, one streamed chunk at a time.

The narrator writes **bold**, *italic*, `code`, ## headings and > quotes. A Tk text
widget knows nothing about markdown, so without this the asterisks show up verbatim.

Text arrives from the network in small chunks, so a marker can be split across two
of them (`**Vrb` … `no**`). The formatter therefore holds back everything from an
unfinished marker and releases it only once its meaning is settled.

Deliberately free of tkinter so it can be tested without opening a window.
"""

import re

HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)$")
QUOTE = re.compile(r"^\s*>\s?(.*)$")
FENCE = re.compile(r"^\s*```")            # fence around a code block
PARTIAL_FENCE = re.compile(r"^`{1,2}$")
# Asterisks are left out on purpose so dividers cannot clash with italics.
DIVIDER = re.compile(r"^\s*([-_]\s*){3,}$")
PARTIAL_DIVIDER = re.compile(r"^[\s\-_]+$")
DIVIDER_WIDTH = 48

# Style names; the window maps them to Tk text tags of the same name.
BOLD, ITALIC, CODE, QUOTED, TITLE, RULE = "bold", "italic", "code", "quote", "heading", "divider"


def _safe_end(text):
    """How far the text can be shown without cutting a marker in half."""
    end = len(text)

    # An unfinished line that looks like a heading, quote or divider: wait for the
    # whole line, otherwise only its first half would get the style.
    line_start = text.rfind("\n") + 1
    last_line = text[line_start:]
    if last_line.lstrip().startswith(("#", ">")):
        return line_start
    if last_line and PARTIAL_DIVIDER.match(last_line):
        return line_start
    if last_line and PARTIAL_FENCE.match(last_line):   # one or two backticks so far
        return line_start
    if FENCE.match(last_line):
        return line_start

    # Unclosed bold, italic or inline code.
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            closing = text.find("**", i + 2)
            if closing == -1:
                return min(end, i)
            i = closing + 2
        elif text[i] == "*":
            closing = text.find("*", i + 1)
            if closing == -1:
                return min(end, i)
            i = closing + 1
        elif text[i] == "`":
            run = i
            while run < len(text) and text[run] == "`":
                run += 1
            if run - i >= 3:            # block fence -- handled per line, leave it alone
                i = run
                continue
            line_end = text.find("\n", run)
            limit = len(text) if line_end == -1 else line_end
            closing = text.find("`", run, limit)
            if closing != -1:
                i = closing + 1
            elif line_end == -1:        # line is still incomplete, this may yet close
                return min(end, i)
            else:
                i = limit               # never closed on this line, so it was not code
        else:
            i += 1

    return end


def _inline_spans(line):
    """Splits one line into (text, styles) by bold, italic and `code`."""
    spans = []
    i = 0
    while i < len(line):
        if line.startswith("**", i):
            closing = line.find("**", i + 2)
            if closing == -1:
                spans.append((line[i:], ()))
                break
            spans.append((line[i + 2:closing], (BOLD,)))
            i = closing + 2
        elif line[i] == "*":
            closing = line.find("*", i + 1)
            if closing == -1:
                spans.append((line[i:], ()))
                break
            spans.append((line[i + 1:closing], (ITALIC,)))
            i = closing + 1
        elif line[i] == "`":
            closing = line.find("`", i + 1)
            if closing == -1:
                spans.append((line[i:], ()))
                break
            spans.append((line[i + 1:closing], (CODE,)))
            i = closing + 1
        else:
            marks = [pos for pos in (line.find("*", i), line.find("`", i)) if pos != -1]
            if not marks:
                spans.append((line[i:], ()))
                break
            spans.append((line[i:min(marks)], ()))
            i = min(marks)
    return [(text, styles) for text, styles in spans if text]


def _spans(text, state):
    """Converts settled text into a list of (text, styles).

    `state` remembers whether we are inside a ```...``` block, which may span
    several chunks and therefore several calls.
    """
    result = []
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\n")
        newline = raw_line[len(line):]

        if FENCE.match(line):                 # the fence itself is never shown
            state["in_code"] = not state["in_code"]
            continue

        if state["in_code"]:
            result.append((line + newline, (CODE,)))
            continue

        heading = HEADING.match(line)
        if heading:
            result.append((heading.group(2).strip() + newline, (TITLE,)))
            continue

        quote = QUOTE.match(line)
        if quote:
            result.extend((text, styles + (QUOTED,))
                          for text, styles in _inline_spans(quote.group(1)))
            if newline:
                result.append((newline, (QUOTED,)))
            continue

        if line.strip() and DIVIDER.match(line):
            result.append(("─" * DIVIDER_WIDTH + newline, (RULE,)))
            continue

        result.extend(_inline_spans(line))
        if newline:
            result.append((newline, ()))
    return result


class Formatter:
    """Converts incoming text chunks into styled spans."""

    def __init__(self):
        self.buffer = ""
        self.state = {"in_code": False}

    def feed(self, chunk):
        """Returns the spans that are safe to show now."""
        self.buffer += chunk
        cut = _safe_end(self.buffer)
        settled, self.buffer = self.buffer[:cut], self.buffer[cut:]
        return _spans(settled, self.state) if settled else []

    def flush(self):
        """At the end of a reply, releases whatever is still held back."""
        rest, self.buffer = self.buffer, ""
        spans = _spans(rest, self.state) if rest else []
        self.state["in_code"] = False     # an unclosed block must not leak into the next turn
        return spans
