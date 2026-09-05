"""Double-click to start the game, with no console behind it.

The code lives in the game/ package next to this file; this is only a launcher --
the .pyw extension makes Windows open it with pythonw.exe.

The filename is what the player sees on their desktop, which is why it reads as a
title rather than as a module name.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import gui

if __name__ == "__main__":
    try:
        gui.AdventureWindow().mainloop()
    except Exception:
        # Without a console the traceback would be lost -- show it in a window instead.
        import tkinter as tk
        import traceback
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(f"{gui.TITLE} spadlo", traceback.format_exc())
        sys.exit(1)
