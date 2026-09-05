"""Window version of the text adventure (console.py is the terminal one).

It opens on a setup screen: world preset, free-text description, genre, tone,
difficulty, dice system and the characters. That turns into the brief for the
narrator, and only then does the game start.

Narration and dice come from whichever engine is available -- engine_claude_code
(subscription) or engine_api (API credit). The engine call runs on a background
thread so the window never freezes, and results come back through a queue.

Run:  python -m game.gui   (or double-click "The Narrator.pyw")
"""

import ctypes
import dataclasses
import os
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import (ROOT, engine_api, engine_claude_code, markdown_stream, rules_loader,
               storage, world)

# "auto"        -- try the subscription (Claude Code) first, then an API key
# "claude-code" -- always the subscription
# "api"         -- always the API key
BACKEND = "auto"

BG = "#1e1f26"
PANEL = "#2a2c37"
HOVER = "#343747"
TEXT = "#e6e6ea"
MUTED = "#9a9cab"
PLAYER = "#7cc4ff"
DICE = "#ffb86c"
NOTICE = "#8d8f9e"
CODE = "#9fd0a8"
SCROLLBAR = "#3d4050"
SCROLLBAR_ACTIVE = "#525668"

# Text tags: the styles markdown_stream produces plus the ones we add ourselves.
NARRATOR_TAG, PLAYER_TAG, DICE_TAG, NOTICE_TAG = "narrator", "player", "dice", "notice"


TITLE = "The Narrator"
ICON = os.path.join(ROOT, "assets", "narrator.ico")


class AdventureWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.set_icon()
        self.configure(bg=BG)
        self.minsize(660, 560)

        self.font_story = tkfont.Font(family="Georgia", size=12)
        self.font_bold = tkfont.Font(family="Georgia", size=12, weight="bold")
        self.font_italic = tkfont.Font(family="Georgia", size=12, slant="italic")
        self.font_story_heading = tkfont.Font(family="Georgia", size=14, weight="bold")
        self.font_ui = tkfont.Font(family="Segoe UI", size=10)
        self.font_heading = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.font_small = tkfont.Font(family="Segoe UI", size=9)
        self.font_dice = tkfont.Font(family="Consolas", size=11, weight="bold")
        self.font_code = tkfont.Font(family="Consolas", size=11)

        self.messages = []
        self.settings = world.Settings()
        self.engine = engine_api
        self.costs = engine_api.Costs()
        self.source = ""
        self.events = queue.Queue()
        self.formatter = markdown_stream.Formatter()
        self.busy = False
        self.client = None
        self.system = None
        # Remembered rather than measured: while text streams in fast, yview() still
        # reports the old position, so the view would come unstuck from the end
        # once and never return.
        self.stick_to_bottom = True

        self.style_scrollbar()
        self.setup_screen = self.build_setup_screen()
        self.game_screen = self.build_game_screen()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.drain_events)
        self.show_setup()

    def set_icon(self):
        """Puts the d20 from assets/narrator.ico in the title bar and on the taskbar.

        The taskbar needs the second half: it groups windows by an application id,
        and without one of our own Windows files us under pythonw.exe and shows the
        Python logo there no matter what the window itself says.

        A missing or unreadable icon is not worth refusing to start over, so the game
        just runs with the default one.
        """
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("the.narrator.game")
        except (AttributeError, OSError):
            pass          # not Windows, or an older one -- only the taskbar loses out
        try:
            self.iconbitmap(default=ICON)
        except tk.TclError:
            pass

    # ---------- setup screen ----------

    def build_setup_screen(self):
        frame = tk.Frame(self, bg=BG, padx=24, pady=18)

        tk.Label(frame, text="Nové dobrodružství", font=self.font_heading,
                 bg=BG, fg=TEXT).pack(anchor="w")

        # --- presets ---
        self.small_label(frame, "Začni z předlohy").pack(anchor="w", pady=(14, 4))
        presets = tk.Frame(frame, bg=BG)
        presets.pack(anchor="w", fill="x")
        for i, name in enumerate(world.PRESETS):
            tk.Button(
                presets, text=name, font=self.font_ui,
                command=lambda n=name: self.apply_preset(n),
                bg=PANEL, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
                relief="flat", borderwidth=0, highlightthickness=0, padx=10, pady=5,
            ).grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 6), pady=3)
        for column in range(3):
            presets.columnconfigure(column, weight=1)

        # --- the player's own world description ---
        self.small_label(frame, "Svět a výchozí situace – klidně přepiš vlastními slovy").pack(
            anchor="w", pady=(14, 4))
        world_box, self.world_box = self.scrollable_text(
            frame, height=8, wrap="word", font=self.font_ui,
            bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
            borderwidth=0, highlightthickness=0, padx=10, pady=8,
        )
        world_box.configure(highlightthickness=1, highlightbackground=HOVER, highlightcolor=PLAYER)
        world_box.pack(fill="x")

        # --- dropdowns ---
        options = tk.Frame(frame, bg=BG)
        options.pack(fill="x", pady=(14, 0))

        blank = world.Settings()
        self.genre = tk.StringVar(value=blank.genre.label)
        self.tone = tk.StringVar(value=blank.tone.label)
        self.difficulty = tk.StringVar(value=blank.difficulty.label)
        self.dice_system = tk.StringVar(value=blank.system.label)
        self.player_count = tk.IntVar(value=blank.players)

        # The labels come from the enums, so adding a genre means one line in world.py
        # instead of keeping a list here in sync with the one over there.
        for column, (title, variable, choices) in enumerate((
            ("Žánr", self.genre, world.Genre),
            ("Tón", self.tone, world.Tone),
            ("Obtížnost", self.difficulty, world.Difficulty),
            ("Hody", self.dice_system, world.DiceSystem),
        )):
            self.dropdown(options, title, variable, choices.labels()).grid(
                row=0, column=column, sticky="w", padx=(0, 18))

        count = tk.Frame(options, bg=BG)
        count.grid(row=0, column=4, sticky="w")
        self.small_label(count, "Postav").pack(anchor="w")
        tk.Spinbox(
            count, from_=1, to=world.MAX_CHARACTERS, textvariable=self.player_count, width=3,
            font=self.font_ui, bg=PANEL, fg=TEXT, buttonbackground=PANEL,
            relief="flat", highlightthickness=0, justify="center",
            command=self.refresh_character_rows,
        ).pack(anchor="w", pady=(2, 0))
        self.player_count.trace_add("write", lambda *_: self.refresh_character_rows())

        # --- characters ---
        self.small_label(frame, "Postavy – nech prázdné a vypravěč je vytvoří s tebou").pack(
            anchor="w", pady=(14, 4))
        self.characters_frame = tk.Frame(frame, bg=BG)
        self.characters_frame.pack(fill="x")
        self.character_rows = []
        self.refresh_character_rows()

        tk.Button(
            frame, text="Začít dobrodružství", command=self.start_game,
            font=tkfont.Font(family="Segoe UI", size=12), bg=PANEL, fg=TEXT,
            activebackground=HOVER, activeforeground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0, pady=10,
        ).pack(fill="x", pady=(18, 0))

        self.setup_status = tk.Label(frame, text="", font=self.font_small, bg=BG, fg=MUTED)
        self.setup_status.pack(anchor="w", pady=(8, 0))

        return frame

    def style_scrollbar(self):
        """The default Windows scrollbar is drawn natively and ignores our colours.

        The 'clam' theme is the only built-in one that lets them be set, and a custom
        layout drops the arrows at both ends, leaving just a thin thumb.
        """
        style = ttk.Style(self)
        style.theme_use("clam")
        style.layout("Thin.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
            }),
        ])
        style.configure(
            "Thin.Vertical.TScrollbar",
            troughcolor=BG, background=SCROLLBAR, bordercolor=BG,
            lightcolor=SCROLLBAR, darkcolor=SCROLLBAR,
            relief="flat", borderwidth=0, width=10, arrowsize=0,
        )
        style.map(
            "Thin.Vertical.TScrollbar",
            background=[("pressed", SCROLLBAR_ACTIVE), ("active", SCROLLBAR_ACTIVE)],
        )

    def scrollable_text(self, parent, on_scroll=None, **options):
        """A text box with our own thin scrollbar. Returns (wrapper, text box).

        `on_scroll` is called whenever the player moves the view themselves, which is
        how the story keeps track of whether it may follow along to the bottom.
        """
        wrapper = tk.Frame(parent, bg=options.get("bg", PANEL))
        box = tk.Text(wrapper, **options)

        def scroll(*args):
            box.yview(*args)
            if on_scroll:
                on_scroll()

        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=scroll,
                                  style="Thin.Vertical.TScrollbar")
        box.configure(yscrollcommand=scrollbar.set)
        box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y", padx=(2, 3), pady=3)
        if on_scroll:
            for event in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Prior>", "<Next>",
                          "<Up>", "<Down>", "<Home>", "<End>", "<ButtonRelease-1>"):
                # after_idle: at the moment of the keypress the view has not moved yet.
                box.bind(event, lambda _=None: self.after_idle(on_scroll), add="+")
        return wrapper, box

    def small_label(self, parent, text):
        return tk.Label(parent, text=text, font=self.font_small, bg=BG, fg=MUTED)

    def dropdown(self, parent, title, variable, choices):
        """A small caption with a dropdown menu underneath."""
        wrapper = tk.Frame(parent, bg=BG)
        self.small_label(wrapper, title).pack(anchor="w")
        menu = tk.OptionMenu(wrapper, variable, *choices)
        menu.config(font=self.font_ui, bg=PANEL, fg=TEXT, activebackground=HOVER,
                    activeforeground=TEXT, relief="flat", borderwidth=0,
                    highlightthickness=0, anchor="w", width=20)
        menu["menu"].config(bg=PANEL, fg=TEXT, activebackground=HOVER, font=self.font_ui)
        menu.pack(anchor="w", pady=(2, 0))
        return wrapper

    def refresh_character_rows(self):
        """Redraws the character rows for the chosen count, keeping what was typed."""
        try:
            wanted = max(1, min(world.MAX_CHARACTERS, self.player_count.get()))
        except tk.TclError:
            return

        while len(self.character_rows) > wanted:
            _, _, row = self.character_rows.pop()
            row.destroy()

        while len(self.character_rows) < wanted:
            row = tk.Frame(self.characters_frame, bg=BG)
            row.pack(fill="x", pady=2)
            name = tk.Entry(row, font=self.font_ui, bg=PANEL, fg=TEXT,
                            insertbackground=TEXT, relief="flat", highlightthickness=1,
                            highlightbackground=HOVER, highlightcolor=PLAYER, width=18)
            name.pack(side="left", ipady=5, padx=(0, 6))
            description = tk.Entry(row, font=self.font_ui, bg=PANEL, fg=TEXT,
                                   insertbackground=TEXT, relief="flat", highlightthickness=1,
                                   highlightbackground=HOVER, highlightcolor=PLAYER)
            description.pack(side="left", fill="x", expand=True, ipady=5)
            self.character_rows.append((name, description, row))

    def apply_preset(self, name):
        # A preset describes a world, not a party -- characters already typed in stay.
        current = self.collect_settings()
        preset = dataclasses.replace(world.PRESETS[name],
                                     players=current.players, characters=current.characters)
        self.fill_settings(preset)
        self.setup_status.config(text=f"Načtena předloha „{name}“ – uprav si ji, jak chceš.")

    def collect_settings(self):
        """Reads the setup screen into a Settings record.

        The dropdowns hold labels, so each one is turned back into its enum member;
        an unknown label would raise rather than quietly become the default.
        """
        return world.Settings(
            world=self.world_box.get("1.0", "end").strip(),
            genre=world.Genre.from_label(self.genre.get()),
            tone=world.Tone.from_label(self.tone.get()),
            difficulty=world.Difficulty.from_label(self.difficulty.get()),
            system=world.DiceSystem.from_label(self.dice_system.get()),
            players=self.player_count.get(),
            characters=[world.Character(name.get().strip(), description.get().strip())
                        for name, description, _ in self.character_rows],
        )

    def fill_settings(self, settings):
        """The opposite of collect_settings -- used by presets and by loading a game."""
        self.world_box.delete("1.0", "end")
        self.world_box.insert("1.0", settings.world)
        self.genre.set(settings.genre.label)
        self.tone.set(settings.tone.label)
        self.difficulty.set(settings.difficulty.label)
        self.dice_system.set(settings.system.label)
        self.player_count.set(settings.players)
        self.refresh_character_rows()
        for (name, description, _), character in zip(self.character_rows, settings.characters):
            name.delete(0, "end")
            name.insert(0, character.name)
            description.delete(0, "end")
            description.insert(0, character.description)

    def show_setup(self):
        self.game_screen.pack_forget()
        self.setup_screen.pack(fill="both", expand=True)
        self.geometry("900x780")

    # ---------- game screen ----------

    def build_game_screen(self):
        frame = tk.Frame(self, bg=BG)

        toolbar = tk.Frame(frame, bg=BG, padx=12, pady=10)
        toolbar.pack(fill="x")
        for caption, action in (("Nová hra", self.back_to_setup),
                                ("Uložit", self.save_game), ("Načíst", self.load_game)):
            tk.Button(
                toolbar, text=caption, command=action, font=self.font_ui,
                bg=PANEL, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
                relief="flat", borderwidth=0, highlightthickness=0, padx=14, pady=5,
            ).pack(side="left", padx=(0, 8))
        self.status_label = tk.Label(toolbar, text="", font=self.font_ui, bg=BG, fg=MUTED)
        self.status_label.pack(side="right")

        story_wrapper, self.story = self.scrollable_text(
            frame, on_scroll=self.on_player_scroll, wrap="word", font=self.font_story,
            bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", borderwidth=0,
            highlightthickness=0, padx=18, pady=14, spacing1=2, spacing3=6,
        )
        story_wrapper.pack(fill="both", expand=True, padx=12)
        self.story.configure(state="disabled")
        self.story.tag_configure(NARRATOR_TAG, foreground=TEXT)
        self.story.tag_configure(PLAYER_TAG, foreground=PLAYER, spacing1=10)
        self.story.tag_configure(DICE_TAG, foreground=DICE, font=self.font_dice,
                                 spacing1=6, spacing3=6)
        self.story.tag_configure(NOTICE_TAG, foreground=NOTICE, font=self.font_ui)
        # Styles coming out of the narrator's markdown (see markdown_stream.py).
        self.story.tag_configure(markdown_stream.BOLD, font=self.font_bold)
        self.story.tag_configure(markdown_stream.ITALIC, font=self.font_italic)
        self.story.tag_configure(markdown_stream.CODE, font=self.font_code, foreground=CODE)
        self.story.tag_configure(markdown_stream.QUOTED, font=self.font_italic,
                                 lmargin1=28, lmargin2=28, foreground=MUTED)
        self.story.tag_configure(markdown_stream.TITLE, font=self.font_story_heading,
                                 spacing1=12, spacing3=4)
        self.story.tag_configure(markdown_stream.RULE, foreground=SCROLLBAR,
                                 spacing1=8, spacing3=8)

        bottom = tk.Frame(frame, bg=BG, padx=12, pady=12)
        bottom.pack(fill="x")
        self.entry = tk.Entry(
            bottom, font=self.font_story, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", highlightthickness=1, highlightbackground=HOVER,
            highlightcolor=PLAYER,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _: self.send())
        self.send_button = tk.Button(
            bottom, text="Odeslat", command=self.send, font=self.font_ui,
            bg=PANEL, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0, padx=18, pady=8,
        )
        self.send_button.pack(side="left")

        return frame

    def show_game(self):
        self.setup_screen.pack_forget()
        self.game_screen.pack(fill="both", expand=True)
        self.geometry("900x740")

    # ---------- writing into the window ----------

    def is_at_bottom(self):
        """Is the view at the very end of the story?

        The fraction from yview() alone is not enough: when the last line only
        partly fits (a different DPI or font size), it stays just under 1.0 even
        though the player can see the end. The visibility of the last character decides.
        """
        try:
            if self.story.bbox("end-1c") is not None:
                return True
            return self.story.yview()[1] >= 0.999
        except Exception:
            return True

    def write(self, text, tag=NARRATOR_TAG, force_bottom=False):
        """Appends plain text to the story."""
        self.write_spans([(text, ())], tag, force_bottom)

    def write_spans(self, spans, tag=NARRATOR_TAG, force_bottom=False):
        """Appends (text, extra styles) pieces to the story.

        It follows to the bottom only while the player is already there. Once they
        have scrolled up to read, incoming words no longer yank the view away --
        text piles up below and they come back down when they want to.
        """
        if force_bottom:
            self.stick_to_bottom = True
        self.story.configure(state="normal")
        for text, extra_styles in spans:
            self.story.insert("end", text, (tag,) + tuple(extra_styles))
        self.story.configure(state="disabled")
        if self.stick_to_bottom:
            self.story.see("end")

    def on_player_scroll(self):
        """The player moved the view: follow along only if they stayed at the end."""
        self.stick_to_bottom = self.is_at_bottom()

    def clear_story(self):
        self.story.configure(state="normal")
        self.story.delete("1.0", "end")
        self.story.configure(state="disabled")

    def refresh_status(self, text=None):
        if text is None:
            text = "Vypravěč přemýšlí…" if self.busy else "Jsi na řadě"
        parts = [text]
        if self.source:
            parts.append(self.source)
        parts.append(self.costs.status_text())
        self.status_label.config(text="   ·   ".join(parts))

    # ---------- starting a game ----------

    def brief(self):
        """The world settings plus the .md rules, so they can be changed without code."""
        return world.build_brief(self.settings) + rules_loader.load()

    def select_backend(self, brief, session_id=None):
        """Decides where the tokens come from. Returns True on success.

        Each engine has its own version of the dice rules (a tool call versus a
        marker in the text), so the brief is attached to whichever base is right.
        """
        if BACKEND in ("auto", "claude-code") and engine_claude_code.find_claude():
            try:
                self.engine = engine_claude_code
                # The brief does not belong in the system prompt here: that one is
                # passed as a command-line argument, and Windows caps those at 8191
                # characters. The world and rules go through the pipe instead.
                self.system = engine_claude_code.build_system_prompt()
                self.client = engine_claude_code.ClaudeCodeNarrator(
                    session_id=session_id, system=self.system, briefing=brief).start()
                self.costs = engine_claude_code.SubscriptionCosts()
                self.source = "předplatné"
                return True
            except Exception as error:
                if BACKEND == "claude-code":
                    self.show_start_error(f"Claude Code se nepodařilo spustit:\n{error}")
                    return False
                self.write(f"[Claude Code nedostupný ({error}), zkouším API klíč.]\n", NOTICE_TAG)

        if BACKEND == "claude-code":
            self.show_start_error("Nenašel jsem Claude Code.\n"
                                  "Nainstaluješ ho: npm install -g @anthropic-ai/claude-code")
            return False

        if not engine_api.AVAILABLE:
            self.show_start_error("Není z čeho hrát: Claude Code není k dispozici "
                                  f"a chybí i knihovna pro API.\n{engine_api.MISSING_PACKAGE}")
            return False

        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.show_start_error(
                "Není z čeho hrát: Claude Code není k dispozici a chybí i API klíč.\n"
                'Nastav ho: setx ANTHROPIC_API_KEY "sk-ant-..."')
            return False

        self.engine = engine_api
        self.system = engine_api.build_system_prompt(brief)
        self.client = engine_api.create_client()
        self.costs = engine_api.Costs()
        self.source = "API kredit"
        return True

    def show_start_error(self, text):
        self.setup_status.config(text=text.replace("\n", "  "))
        messagebox.showerror("Nelze začít", text)

    def start_game(self):
        if self.busy:
            return
        self.settings = self.collect_settings()
        self.stop_backend()
        # The brief has to be ready now -- Claude Code gets it as the process starts.
        if not self.select_backend(self.brief()):
            return

        self.clear_story()
        self.messages = [{"role": "user", "content": world.first_message(self.settings)}]
        self.show_game()
        self.run_narrator()

    def back_to_setup(self):
        if self.busy:
            return
        if self.messages and not messagebox.askyesno(
                "Nová hra", "Zahodit rozehraný příběh a vrátit se do nastavení?"):
            return
        self.stop_backend()
        self.messages = []
        self.show_setup()

    # ---------- playing ----------

    def send(self):
        if self.busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        # Players want to see their own action even if they scrolled up.
        self.write(f"\n▸ {text}\n\n", PLAYER_TAG, force_bottom=True)
        self.messages.append({"role": "user", "content": text})
        self.run_narrator()

    def run_narrator(self):
        self.busy = True
        self.set_input_enabled(False)
        self.refresh_status()
        threading.Thread(target=self.work_in_background, daemon=True).start()

    def work_in_background(self):
        """Runs off the main thread -- may touch the queue only, never a widget."""
        try:
            self.engine.narrator_turn(
                self.client, self.messages, self.costs,
                write=lambda chunk: self.events.put(("text", chunk)),
                announce=lambda text: self.events.put(("notice", text)),
                system=self.system,
            )
        except Exception as error:
            # engine_api knows which exceptions carry an API status code and which
            # do not; the window only shows whatever line comes back.
            self.events.put(("error", engine_api.describe_error(error)))
        finally:
            self.events.put(("done", None))

    def drain_events(self):
        """The only place that writes into the window -- runs on the main thread."""
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "text":
                    # The narrator's markdown becomes real formatting here.
                    self.write_spans(self.formatter.feed(payload))
                elif kind == "notice":
                    self.write_spans(self.formatter.flush())
                    self.write(f"\n{payload}\n\n", DICE_TAG if "🎲" in payload else NOTICE_TAG)
                elif kind == "error":
                    self.write_spans(self.formatter.flush())
                    self.write(f"\n[{payload}]\n\n", NOTICE_TAG)
                    if self.messages and self.messages[-1]["role"] == "user":
                        self.messages.pop()
                elif kind == "done":
                    # Whatever the formatter still holds back has to come out.
                    self.write_spans(self.formatter.flush())
                    self.busy = False
                    self.set_input_enabled(True)
                    self.refresh_status()
        except queue.Empty:
            pass
        self.after(50, self.drain_events)

    def set_input_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.entry.config(state=state)
        self.send_button.config(state=state)
        if enabled:
            self.entry.focus_set()

    # ---------- saving ----------

    def save_game(self):
        if self.busy or not self.messages:
            return
        storage.save(
            self.messages,
            announce=lambda text: self.write(f"\n{text}\n\n", NOTICE_TAG),
            session_id=getattr(self.client, "session_id", None),
            settings=self.settings,
        )

    def load_game(self):
        if self.busy:
            return
        data = storage.load(announce=lambda _: None)
        if not data:
            messagebox.showinfo("Načtení", f"Soubor {storage.SAVE_PATH} neexistuje.")
            return

        try:
            self.settings = world.Settings.from_json(data.get("settings"))
        except (ValueError, TypeError) as error:
            # A hand-edited or truncated save should say so, not half-load a game.
            messagebox.showerror("Načtení", f"Uložená hra je poškozená:\n{error}")
            return
        self.fill_settings(self.settings)

        self.stop_backend()
        if not self.select_backend(self.brief(), session_id=data.get("session_id")):
            return

        self.messages = data["messages"]
        # The narrator starts with an empty head, so we hand it the story ourselves.
        if self.engine is engine_claude_code and hasattr(self.client, "recap"):
            self.client.recap = engine_claude_code.build_recap(self.messages)
        self.clear_story()
        self.render_history()
        self.show_game()
        self.refresh_status()
        self.set_input_enabled(True)

    def render_history(self):
        for message in self.messages:
            content = message["content"]
            if message["role"] == "user":
                if isinstance(content, str):
                    self.write(f"\n▸ {content}\n\n", PLAYER_TAG)
                continue
            for block in content:
                if block.get("type") == "text":
                    # A loaded game goes through formatting too, so it looks the same.
                    formatter = markdown_stream.Formatter()
                    self.write_spans(formatter.feed(block["text"]) + formatter.flush())

    def stop_backend(self):
        if hasattr(self.client, "stop"):
            try:
                self.client.stop()
            except Exception:
                pass
        self.client = None

    def on_close(self):
        if self.busy:
            if not messagebox.askyesno("Ukončit", "Vypravěč právě píše. Přesto zavřít?"):
                return
        self.stop_backend()   # otherwise the `claude` subprocess would linger
        self.destroy()


if __name__ == "__main__":
    AdventureWindow().mainloop()
