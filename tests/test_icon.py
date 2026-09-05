"""The icon file the window and the desktop shortcut point at.

This exists because the icon file was once found sitting on disk at zero bytes. Nothing
complained: Windows just falls back to its default icon, so the only symptom was
"I can't see the icon". The file is now a hand-kept asset with no generator behind
it, which makes a silent check like this worth more, not less.
"""

import os
import struct

from harness import check, finish

from game import gui

EXPECTED_SIZES = [16, 24, 32, 48, 64, 128, 256]
BODY = (255, 184, 108)          # amber, the same colour dice rolls use in the window

check("the window knows where the icon is", gui.ICON.endswith("narrator.ico"), gui.ICON)
check("the icon file exists", os.path.exists(gui.ICON), gui.ICON)

if not os.path.exists(gui.ICON):
    finish()

data = open(gui.ICON, "rb").read()
check("the icon file is not empty", len(data) > 0, len(data))

reserved, kind, count = struct.unpack("<HHH", data[:6])
check("it starts with an icon header", (reserved, kind) == (0, 1), (reserved, kind))
check("it holds every size", count == len(EXPECTED_SIZES), count)

sizes, entries = [], {}
for i in range(count):
    entry = data[6 + i * 16:22 + i * 16]
    width, height, colours, _, planes, bpp, length, offset = struct.unpack("<BBBBHHII", entry)
    stored = width or 256                      # a 256 px entry records its size as 0
    sizes.append(stored)
    entries[stored] = (offset, length)
    check(f"entry {stored} px is square", width == height, (width, height))
    check(f"entry {stored} px is 32-bit", bpp == 32, bpp)
    check(f"entry {stored} px lies inside the file", offset + length <= len(data),
          (offset, length, len(data)))
    header_size, w, h = struct.unpack("<Iii", data[offset:offset + 12])
    check(f"entry {stored} px has a bitmap header", header_size == 40, header_size)
    check(f"entry {stored} px stores a mask below the image", h == 2 * w, (w, h))

check("the sizes are the expected ones", sizes == EXPECTED_SIZES, sizes)


def pixel(size, x, y):
    """One pixel of an entry: BGRA, and the rows are stored bottom-up."""
    offset, _ = entries[size]
    start = offset + 40 + ((size - 1 - y) * size + x) * 4
    b, g, r, a = data[start:start + 4]
    return (r, g, b, a)


# Not blank: the die's body in the middle, nothing in the corner.
check("the centre is the die's body", pixel(32, 16, 16)[:3] == BODY, pixel(32, 16, 16))
check("the corner is transparent", pixel(32, 0, 0)[3] == 0, pixel(32, 0, 0))
check("the big size is drawn too", pixel(128, 64, 64)[:3] == BODY, pixel(128, 64, 64))
check("the small size is drawn too", pixel(16, 8, 8)[:3] == BODY, pixel(16, 8, 8))

finish()
