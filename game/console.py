"""Terminal front-end for the adventure. The window version is gui.py.

Run:      python -m game.console
Needs:    pip install anthropic  +  the ANTHROPIC_API_KEY environment variable

This front-end only speaks to the API, so unlike the window it does need the package.
"""

import os
import sys

from . import engine_api, storage


def print_last_narration(messages):
    """Shows the last piece of narration so a loaded game has some context."""
    for message in reversed(messages):
        if message["role"] == "assistant":
            for block in message["content"]:
                if block.get("type") == "text":
                    print(block["text"])
            return


def _load_saved_game():
    """Offers the saved game, if there is one. Returns its messages or []."""
    if not os.path.exists(storage.SAVE_PATH):
        return []
    if input("Nalezena ulozena hra. Nacist? (a/n): ").strip().lower() not in ("a", "ano"):
        return []
    messages = storage.load_messages() or []
    if messages:
        print()
        print_last_narration(messages)
    return messages


def main():
    if not engine_api.AVAILABLE:
        sys.exit(engine_api.MISSING_PACKAGE)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "Neni nastavena promenna ANTHROPIC_API_KEY.\n"
            "Klic ziskas na https://platform.claude.com a nastavis prikazem:\n"
            '  setx ANTHROPIC_API_KEY "sk-ant-..."   (pak otevri novy terminal)'
        )

    client = engine_api.create_client()
    costs = engine_api.Costs()

    print("=" * 60)
    print("  DOBRODRUZSTVI  --  vypravi Claude, kostky hazi program")
    print("=" * 60)
    print("Prikazy:  /ulozit   /nacist   /cena   /konec\n")

    messages = _load_saved_game()
    if not messages:
        messages = [
            {
                "role": "user",
                "content": "Zacnime novou hru. Pomoz mi vytvorit postavu a zacni prvni scenu.",
            }
        ]
        print()
        engine_api.narrator_turn(client, messages, costs)

    while True:
        try:
            command = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSbohem, dobrodruhu.")
            print(costs.summary())
            return

        if not command:
            continue
        if command == "/konec":
            print("Sbohem, dobrodruhu.")
            print(costs.summary())
            return
        if command == "/ulozit":
            storage.save(messages)
            continue
        if command == "/nacist":
            loaded = storage.load_messages()
            if loaded:
                messages = loaded
                print()
                print_last_narration(messages)
            continue
        if command == "/cena":
            print(costs.summary())
            continue

        messages.append({"role": "user", "content": command})
        print()
        try:
            engine_api.narrator_turn(client, messages, costs)
        except Exception as error:
            print(f"\n[{engine_api.describe_error(error)}]")
            messages.pop()      # the turn never happened, so drop the action again


if __name__ == "__main__":
    main()
