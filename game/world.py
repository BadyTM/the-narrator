"""World settings: the closed option lists, the presets, and the brief they build.

Two shapes live here. `Settings` is a record -- one game's worth of choices. The four
enums are closed lists: a genre can only ever be one of four things, and each member
carries everything about itself at once, so adding one means editing one line.

    Genre.FANTASY.key           "fantasy"        stored in the save file
    Genre.FANTASY.label         "Fantasy"        shown in the window
    Genre.FANTASY.description   "Fantasy. ..."   sent to the narrator

The descriptions are Czech because they go straight into the prompt and the narrator
tells the story in Czech. Only the code around them is English.

Deliberately free of tkinter so it can be tested without opening a window.
"""

from dataclasses import dataclass, field
from enum import Enum

MAX_CHARACTERS = 4


class Choice(Enum):
    """Base for the four option lists: one key, one label, one description.

    An Enum with no members of its own can be subclassed, which is what lets all
    four lists share the lookups below.
    """

    def __init__(self, key, label, description):
        self.key = key
        self.label = label
        self.description = description

    @classmethod
    def from_key(cls, key):
        """The member stored under this key. Raises ValueError on anything else.

        Deliberately strict: a typo used to fall back to the default silently, so a
        preset saying "sciffi" quietly produced an everyday world instead of sci-fi.
        A game that starts wrong is worse than one that refuses to start.
        """
        for member in cls:
            if member.key == key:
                return member
        raise ValueError(f"{cls.__name__}: neznamy klic {key!r}, "
                         f"znam jen {[m.key for m in cls]}")

    @classmethod
    def from_label(cls, label):
        """The member shown under this label in the window."""
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"{cls.__name__}: neznamy popisek {label!r}")

    @classmethod
    def labels(cls):
        """Every label, in declaration order -- what a dropdown offers."""
        return [member.label for member in cls]


class Genre(Choice):
    REALISTIC = (
        "realisticky", "Realistický",
        "Realistický. Svět funguje přesně jako ten skutečný v zadané době — fyzika, technika, "
        "zbraně, doprava, medicína, úřady, jazyk. Žádná magie, žádné kouzlení, žádné rituály, "
        "které fungují, žádné jiné světy ani přesuny do nich. Když zadání obsahuje jednu "
        "nereálnou věc (třeba zombie), platí právě ta jedna a nic dalšího se k ní nepřidává — "
        "všechno ostatní kolem ní je všední realita. Postavy umí to, co by uměly ve skutečnosti.",
    )
    FANTASY = (
        "fantasy", "Fantasy",
        "Fantasy. Magie, netvoři a nadpřirozeno jsou běžnou součástí světa a mají svoje pravidla. "
        "Technika odpovídá tomu, co si zadal hráč — jinak předpokládej předindustriální svět.",
    )
    SCIFI = (
        "scifi", "Sci-fi",
        "Sci-fi. Budoucnost, technika, vesmír, umělé inteligence, genetika. Žádná magie: "
        "co vypadá jako zázrak, má technické vysvětlení, i kdyby ho postavy neznaly.",
    )
    HORROR = (
        "horor", "Mysteriózní horor",
        "Mysteriózní horor. Svět je na první pohled všední a přesně takový, jaký zadal hráč, "
        "ale něco v něm nesedí. Nadpřirozeno drž ve stínu, nevysvětluj ho a nedělej z něj systém "
        "kouzel. Míň je víc: jedna nevysvětlitelná věc dělá větší hrůzu než deset.",
    )


class Tone(Choice):
    HEROIC = ("hrdinsky", "Hrdinský",
              "Hrdinský a dobrodružný. Postavy jsou schopné, svět stojí za záchranu.")
    GRITTY = ("drsny", "Drsný",
              "Drsný a špinavý. Vítězství něco stojí, hrdinové jsou omylní a svět lhostejný.")
    EERIE = ("tajemny", "Tajemný",
             "Tajemný a znepokojivý. Víc otázek než odpovědí, hrůza spíš tušená než viděná.")
    FUNNY = ("humorny", "Humorný",
             "Odlehčený a vtipný. Absurdní situace, ale pravidla i nebezpečí platí vážně.")


class Difficulty(Choice):
    GENTLE = ("mirna", "Mírná",
              "Mírná. Neúspěch posouvá příběh jinam, nezabíjí. "
              "Smrt postavy jen když si o ni hráč řekne.")
    NORMAL = ("normalni", "Normální",
              "Normální. Chyby bolí, smrt je možná po varování a špatném rozhodnutí.")
    HARSH = ("kruta", "Krutá",
             "Krutá. Jedna špatná volba může postavu stát život. Nevaruj dvakrát.")


class DiceSystem(Choice):
    FREEFORM = (
        "volny", "Volný – bez statů",
        "Žádné staty. O úspěchu rozhoduje jediný hod 1d20 podle toho, jak riskantní akce je: "
        "snadné 8+, běžné 12+, těžké 16+, skoro nemožné 19+. Bonus přidej podle toho, "
        "jestli postavě situace sedí (+2 až +4).",
    )
    SIMPLE = (
        "jednoduchy", "Jednoduchý – 3 vlastnosti",
        "Tři vlastnosti: SÍLA, OBRATNOST, ROZUM. Každá má bonus +1 až +3, hráč si je rozdělí "
        "při tvorbě postavy (celkem +6). Hází se 1d20 + příslušný bonus proti obtížnosti "
        "10 (snadné) / 14 (běžné) / 18 (těžké).",
    )
    DND = (
        "dnd", "Jako D&D – 6 vlastností",
        "Klasických šest vlastností (Síla, Obratnost, Odolnost, Inteligence, Moudrost, Charisma) "
        "s bonusy -1 až +3 a zdatnostmi jako v D&D 5e. Hází se 1d20 + bonus proti SO 10/15/20. "
        "Zranění podle zbraně, životy sleduj.",
    )


@dataclass
class Character:
    """One character the player controls. Both fields may be empty."""

    name: str = ""
    description: str = ""

    @property
    def described(self):
        """Did the player type anything at all into this row?"""
        return bool(self.name.strip() or self.description.strip())

    def as_line(self, index=1):
        """The '- Name: description' line the narrator gets."""
        name = self.name.strip() or f"Postava {index}"
        description = self.description.strip()
        return f"- {name}" + (f": {description}" if description else "")

    def to_json(self):
        return {"name": self.name, "description": self.description}

    @classmethod
    def from_json(cls, data):
        return cls(name=(data or {}).get("name", ""),
                   description=(data or {}).get("description", ""))


@dataclass
class Settings:
    """Everything one game is set up with.

    The whole shape lives here, so this is the only place to look when you want to
    know what a game consists of -- and the only place that can clamp the values.
    """

    world: str = ""
    genre: Genre = Genre.REALISTIC
    tone: Tone = Tone.HEROIC
    difficulty: Difficulty = Difficulty.NORMAL
    system: DiceSystem = DiceSystem.FREEFORM
    players: int = 1
    characters: list = field(default_factory=list)

    def __post_init__(self):
        # Validation belongs to the data, not to whoever happens to build it. The
        # window and the brief used to clamp this separately.
        self.players = max(1, min(MAX_CHARACTERS, int(self.players)))
        self.characters = [c if isinstance(c, Character) else Character(**c)
                           for c in self.characters]

    @property
    def described_characters(self):
        """Only the rows the player actually filled in."""
        return [c for c in self.characters if c.described]

    def to_json(self):
        """A plain dict for the save file; enums are stored by their key."""
        return {
            "world": self.world,
            "genre": self.genre.key,
            "tone": self.tone.key,
            "difficulty": self.difficulty.key,
            "system": self.system.key,
            "players": self.players,
            "characters": [c.to_json() for c in self.characters],
        }

    @classmethod
    def from_json(cls, data):
        """Rebuilds settings from a save file. Raises ValueError on an unknown key."""
        data = data or {}
        blank = cls()
        return cls(
            world=data.get("world", blank.world),
            genre=Genre.from_key(data["genre"]) if "genre" in data else blank.genre,
            tone=Tone.from_key(data["tone"]) if "tone" in data else blank.tone,
            difficulty=(Difficulty.from_key(data["difficulty"])
                        if "difficulty" in data else blank.difficulty),
            system=DiceSystem.from_key(data["system"]) if "system" in data else blank.system,
            players=data.get("players", blank.players),
            characters=[Character.from_json(c) for c in data.get("characters", [])],
        )


PRESETS = {
    "Klasická fantasy": Settings(
        world=(
            "Království Aldheim po dvaceti letech míru, který začíná praskat ve švech. "
            "Na severu se v horách probudilo něco, co tam po staletí spalo, a vesnice "
            "na okraji divočiny přestávají odpovídat. V hlavním městě to nikoho nezajímá, "
            "protože král umírá a jeho tři děti se už teď dělí o trůn.\n\n"
            "Magie existuje, je vzácná a lidé jí nedůvěřují."
        ),
        genre=Genre.FANTASY, tone=Tone.HEROIC,
        difficulty=Difficulty.NORMAL, system=DiceSystem.SIMPLE,
    ),
    "Temné podzemí": Settings(
        world=(
            "Pod opuštěným klášterem se otevřela chodba, která tam včera ještě nebyla. "
            "Vede dolů. Všichni, kdo do ní vstoupili před vámi, se nevrátili — až na jednoho, "
            "který od té doby nemluví a kreslí pořád dokola tentýž symbol.\n\n"
            "Svítilna vydrží osm hodin. Cesta zpátky trvá šest."
        ),
        genre=Genre.HORROR, tone=Tone.EERIE,
        difficulty=Difficulty.HARSH, system=DiceSystem.SIMPLE,
    ),
    "Městské intriky": Settings(
        world=(
            "Přístavní město Černá Zátoka, kde se obchoduje se vším včetně lidí. "
            "Tři gildy si dělí přístav, městská rada je koupitelná a někdo začal vraždit "
            "prostředníky — vždy v noci, vždy stejným způsobem, vždy někdo, "
            "kdo věděl příliš mnoho.\n\n"
            "Zbraně se tu tasí až jako poslední možnost. Slova řežou hlouběji."
        ),
        genre=Genre.FANTASY, tone=Tone.GRITTY,
        difficulty=Difficulty.NORMAL, system=DiceSystem.FREEFORM,
    ),
    "Přežití v divočině": Settings(
        world=(
            "Vaše loď ztroskotala na pobřeží, které není na žádné mapě. Přežili jste jen vy "
            "a to, co jste stihli vytáhnout z vraku. Do vnitrozemí vede jediná stezka "
            "a někdo ji udržuje.\n\n"
            "Hlad, zima a zranění jsou tu větší nepřítel než cokoli se zuby."
        ),
        genre=Genre.REALISTIC, tone=Tone.GRITTY,
        difficulty=Difficulty.HARSH, system=DiceSystem.SIMPLE,
    ),
    "Vesmírná stanice": Settings(
        world=(
            "Těžební stanice Kalypso na oběžné dráze plynného obra, tři týdny letu od nejbližší "
            "pomoci. Před dvěma dny přestala odpovídat noční směna v sekci D a systémy hlásí, "
            "že je tam o čtyři lidi víc, než kolik jich tam mělo být.\n\n"
            "Zbraně na palubě oficiálně nejsou."
        ),
        genre=Genre.SCIFI, tone=Tone.EERIE,
        difficulty=Difficulty.NORMAL, system=DiceSystem.FREEFORM,
    ),
    "Prázdný list": Settings(),
}


def build_brief(settings):
    """Builds the block of text describing this game, appended to the system prompt."""
    parts = ["\n\n=== ZADANI TETO HRY ==="]
    # Genre comes first on purpose: it decides what may exist in the world at all.
    parts.append("\nZanr (plati pro celou hru): " + settings.genre.description)

    world = settings.world.strip()
    if world:
        parts.append("\nSvet a vychozi situace:\n" + world)
    else:
        parts.append("\nSvet: vymysli si vlastni, hraci ho nezadali. Predstav ho v prvni scene.")

    parts.append("\nTon vypraveni: " + settings.tone.description)
    parts.append("\nObtiznost: " + settings.difficulty.description)
    parts.append("\nPravidla pro hody: " + settings.system.description)

    if settings.players == 1:
        parts.append("\nPocet postav: jedna. Hraje jeden clovek.")
    else:
        parts.append(
            f"\nPocet postav: {settings.players}. Vsechny ovlada jeden clovek u klavesnice -- "
            "pred kazdou scenou davej najevo, ktera postava je na rade, a nech ho "
            "rozhodovat za vsechny. Postavy spolu mluv a lisi se povahou."
        )

    described = settings.described_characters
    if described:
        lines = [c.as_line(i) for i, c in enumerate(described, 1)]
        parts.append("\nPostavy zadane hracem (pouzij je, nevymysli si jine):\n" + "\n".join(lines))
        if len(described) < settings.players:
            missing = settings.players - len(described)
            parts.append(f"\nZbyvajici postavy ({missing}) dotvor sam podle sveta.")
    else:
        parts.append("\nPostavy nejsou zadane -- pomoz je vytvorit v prvni scene.")

    return "".join(parts)


def first_message(settings):
    """The opening message that gets the game moving.

    The characters are repeated here even though the system prompt already has them:
    without it the narrator's first reply tends to ask for "character sheets"
    instead of starting to play.

    The place is repeated for the same reason. The rule about it lives in the system
    prompt too, yet three test games in a row still opened somewhere else -- the last
    sentence the narrator reads before writing carries far more weight.
    """
    world = settings.world.strip()
    place = (f"\n\nPrvni scena se odehrava presne tady: {world}\n"
             "Zacni na tomhle miste, ne cestou k nemu a ne nekde podobne."
             if world else "")

    described = settings.described_characters
    if described and len(described) >= settings.players:
        lines = [c.as_line(i) for i, c in enumerate(described, 1)]
        return (
            "Hraju za tyhle postavy:\n" + "\n".join(lines) + "\n\n"
            "Tohle je vsechno, co o nich potrebujes vedet. Zadne listy postav, staty ani "
            "cisla po mne nechtej -- co ti chybi, si domysli sam a klidne to rovnou pouzij "
            "v pribehu. Na nic se neptej a zacni prvni scenou." + place
        )

    return (
        "Postavy jeste nemam. Vytvor je se mnou primo v prvni scene: zeptej se jen na to "
        "nejnutnejsi (jmeno a cim postava je), zbytek si domysli a hned zacni hrat." + place
    )
