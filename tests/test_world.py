"""The settings record, the four option enums, the presets and the brief they build."""

import dataclasses

from harness import check, finish

from game import world
from game.world import Character, DiceSystem, Difficulty, Genre, Settings, Tone

# --- the enums are the single source of truth for each option list ---
for choices, expected in ((Genre, 4), (Tone, 4), (Difficulty, 3), (DiceSystem, 3)):
    check(f"{choices.__name__} has {expected} members", len(list(choices)) == expected,
          [m.key for m in choices])
    check(f"{choices.__name__} keys are unique",
          len({m.key for m in choices}) == len(list(choices)))
    check(f"{choices.__name__} labels are unique",
          len({m.label for m in choices}) == len(list(choices)))
    check(f"{choices.__name__} describes every member",
          all(len(m.description) > 20 for m in choices),
          [m.key for m in choices if len(m.description) <= 20])
    check(f"{choices.__name__}.labels() keeps declaration order",
          choices.labels() == [m.label for m in choices])
    for member in choices:
        check(f"{choices.__name__}.from_key({member.key!r}) round-trips",
              choices.from_key(member.key) is member)
        check(f"{choices.__name__}.from_label({member.label!r}) round-trips",
              choices.from_label(member.label) is member)

# A typo used to fall back to the default silently, which produced a wrong world.
for bad in ("sciffi", "", "REALISTICKY", None):
    try:
        Genre.from_key(bad)
        check(f"Genre.from_key({bad!r}) is refused", False, "no error raised")
    except ValueError as error:
        check(f"Genre.from_key({bad!r}) is refused", "neznamy klic" in str(error))

try:
    Tone.from_label("Vtipný")
    check("an unknown label is refused", False, "no error raised")
except ValueError:
    check("an unknown label is refused", True)

# --- the settings record ---
blank = Settings()
check("a blank game is realistic", blank.genre is Genre.REALISTIC, blank.genre)
check("a blank game has one player", blank.players == 1)
check("a blank game has no characters", blank.characters == [])
check("two blank games are equal", Settings() == Settings())

check("too many players are clamped down",
      Settings(players=9).players == world.MAX_CHARACTERS, Settings(players=9).players)
check("too few players are clamped up", Settings(players=0).players == 1)
check("a numeric string still works", Settings(players="3").players == 3)

from_dicts = Settings(characters=[{"name": "Vela", "description": "léčitelka"}])
check("plain dicts become Character records",
      isinstance(from_dicts.characters[0], Character), type(from_dicts.characters[0]))

# --- characters ---
check("an empty row counts as undescribed", not Character().described)
check("a name alone is enough", Character(name="Vela").described)
check("a description alone is enough", Character(description="léčitelka").described)
check("whitespace is not a description", not Character(name="  ").described)
check("a full row becomes one line",
      Character("Vela", "léčitelka").as_line() == "- Vela: léčitelka")
check("a nameless row gets a placeholder",
      Character(description="zloděj").as_line(2) == "- Postava 2: zloděj")

party = Settings(players=2, characters=[Character("Vela", "léčitelka"), Character()])
check("only filled rows count as described", len(party.described_characters) == 1,
      party.described_characters)

# --- saving and loading ---
full = Settings(world="Praha 2026", genre=Genre.SCIFI, tone=Tone.GRITTY,
                difficulty=Difficulty.HARSH, system=DiceSystem.DND, players=2,
                characters=[Character("Lukáš", "programátor")])
as_json = full.to_json()
check("enums are saved by key", as_json["genre"] == "scifi", as_json["genre"])
check("characters are saved as dicts", as_json["characters"][0]["name"] == "Lukáš")
check("the record survives a round trip", Settings.from_json(as_json) == full)
check("an empty file yields a blank game", Settings.from_json({}) == Settings())
check("a missing key falls back to the default",
      Settings.from_json({"world": "Praha"}).genre is Genre.REALISTIC)

try:
    Settings.from_json({"genre": "sciffi"})
    check("a corrupt save is refused", False, "no error raised")
except ValueError:
    check("a corrupt save is refused", True)

# --- presets ---
check("there are six presets", len(world.PRESETS) == 6, list(world.PRESETS))
for name, preset in world.PRESETS.items():
    check(f"preset {name!r} is a Settings record", isinstance(preset, Settings), type(preset))
    check(f"preset {name!r} survives a round trip",
          Settings.from_json(preset.to_json()) == preset)
check("the space station is sci-fi", world.PRESETS["Vesmírná stanice"].genre is Genre.SCIFI)
check("classic fantasy is fantasy", world.PRESETS["Klasická fantasy"].genre is Genre.FANTASY)
check("the blank sheet is a blank game", world.PRESETS["Prázdný list"] == Settings())

# --- the brief ---
brief = world.build_brief(Settings(
    world="Praha, Česká zemědělská univerzita 2026. První den zombie apokalypsy",
    genre=Genre.REALISTIC, tone=Tone.GRITTY, players=2,
    characters=[Character("Lukáš", "programátor"), Character("Petr", "programátor")]))
check("the brief opens with the genre",
      brief.index("Zanr") < brief.index("Svet a vychozi"), brief[:60])
check("the genre forbids magic", "Žádná magie" in brief)
check("the brief carries the world text", "zemědělská univerzita" in brief)
check("the brief carries the tone", "Drsný a špinavý" in brief)
check("the brief carries both characters", "Lukáš" in brief and "Petr" in brief)
check("two players are explained", "Pocet postav: 2" in brief)

lone = world.build_brief(Settings())
check("without a world the narrator invents one", "vymysli si vlastni" in lone)
check("without characters the narrator creates them", "Postavy nejsou zadane" in lone)
check("one player is stated plainly", "Pocet postav: jedna" in lone)

half = world.build_brief(Settings(players=3, characters=[Character("Vela", "léčitelka")]))
check("missing characters are handed to the narrator", "Zbyvajici postavy (2)" in half, half[-200:])

# --- the opening message ---
first = world.first_message(Settings(
    world="Praha, ČZU 2026", players=2,
    characters=[Character("Lukáš", "programátor"), Character("Petr", "programátor")]))
check("the opening message repeats the characters", "Lukáš" in first)
check("the opening message repeats the place", "Prvni scena se odehrava presne tady" in first)
check("it forbids starting on the way there", "ne cestou k nemu" in first)
check("no world, no place sentence", "Prvni scena se odehrava" not in world.first_message(Settings()))
check("without characters it offers to create them",
      "Postavy jeste nemam" in world.first_message(Settings(world="Praha", players=2)))

# --- dataclasses.replace is what the preset button relies on ---
kept = dataclasses.replace(world.PRESETS["Vesmírná stanice"],
                           players=2, characters=[Character("Lukáš", "programátor")])
check("a preset can keep the party", kept.genre is Genre.SCIFI and kept.players == 2)
check("replacing does not touch the preset", world.PRESETS["Vesmírná stanice"].players == 1)

finish()
