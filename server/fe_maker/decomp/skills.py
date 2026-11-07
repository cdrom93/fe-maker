"""Skills (game option `skills`), ported from C-SkillSys into the decomp (plan: docs/competences.md).

C-SkillSys (https://github.com/MokhaLeee/fe8u-cskillsys-kernel, MIT, Mokha and contributors) is a CHAX for the
original ROM; its effects are written in C on the decomp's names, so they are taken here skill by skill, at the commit
`COMMIT`, into the build overlay. Its license text is kept in licenses/cskillsys-MIT.txt.

- Skills of a character or a class: `skills` on their sheets (3 at most each, as C-SkillSys), in the tables
  gCharacterSkillsFem and gClassSkillsFem; SkillTesterFem(unit, n) tests them. Only the skills the project uses are
  compiled, numbered from 1.
- The game's own class abilities (Canto, Steal, Pierce...) are shown as skills too (GAME_SKILLS), their engine untouched.
- Status screen, page 1 (ticket 171, layout of the Skill System's MSS, the user's choice): Str to Res then Mov on
  the left; Con, Aid, Cond, Lead, Talk, "Skills" and 2 rows of 3 icons on the right; the affinity beside the
  name; R shows each skill's text.
- Icons: C-SkillSys's (Contents/Gfx/Sources/SkillIcon, already in the game's icon palette), downloaded once and cached,
  never in this repository; they follow the game's 224 icons, whose lookup table moves to free RAM (ICON_TABLE).
- In-game texts: C-SkillSys's (Contents/Texts/Source/texts), its name on the first line.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..config import config_dir
from . import strmag

REPO = "MokhaLeee/fe8u-cskillsys-kernel"
COMMIT = "fb545870458f3c3629cab6cfb2330c3308d2ce6d"
ICON_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Contents/Gfx/Sources/SkillIcon/{{}}.png"
# The triggered skill's name in battle: Huichelaar's display from the Skill System (CC0), at a fixed commit
SS_REPO = "FireEmblemUniverse/SkillSystem_FE8"
SS_COMMIT = "aefb81278ae814ecc53175f79813bc099dae0346"
BOX_URL = (f"https://raw.githubusercontent.com/{SS_REPO}/{SS_COMMIT}"
           "/EngineHacks/SkillSystem/Internals/Graphics/ProcDisplayTiles.png")
MAX_PER_SHEET = 3
MAX_SHOWN = 6   # page 1: 2 rows of 3 icons (ticket 171)
# learned skills (batch 3, docs/competences.md): 4 per character, in the free debug buffer before ICON_TABLE;
# saved like Magic (strmag.SAVE) in the bonus-map zone of the save memory, after Magic and the temporary bonuses
LEARNED_MAX = 4
LEARN_PER_SHEET = 4   # "learns X at level N" entries per character or class sheet
LEARNED_CHARACTERS = 0x40
LEARNED_TABLE = "0x02028800"
LEARNED_SAVE = 0x480
MAX_SKILLS = 63           # icons after the game's 224, in the 0x120 entries of the moved lookup table


class SkillError(Exception):
    pass


@dataclass(frozen=True)
class Skill:
    id: str               # C-SkillSys's name (its SID_ constant without the prefix)
    kind: str             # stat, battle, order, game
    icon: str             # C-SkillSys's icon file
    text: str             # in-game help text, its name first
    stat: int = -1        # stat skills: 0 Str, 1 Skl, 2 Spd, 3 Def, 4 Res, 5 Lck, 6 Mag
    value: int = 0
    defiant: bool = False  # stat skills: only under 25 % of HP
    code: str = ""        # battle skills: C run in ComputeBattleUnitStats (attacker, defender); proc skills: C run on a
    # hit before its damage (attacker, defender, magic, *attack, *defense)
    after: str = ""       # proc skills: C run on the hit's damage, after the critical roll
    game: str = ""        # game skills: the C condition on `unit`


def _stat(sid, icon, stat, value, defiant, text):
    return Skill(sid, "stat", icon, text, stat, value, defiant)


_LOW = "(attacker->hpInitial * 4 < attacker->unit.maxHP)"
_HALF = "(attacker->unit.maxHP > attacker->unit.curHP * 2)"
_FIRST = "(attacker == &gBattleActor)"
_MAGIC = "((%s)->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE))"

CATALOGUE: tuple[Skill, ...] = (
    _stat("StrBonus", "StrBonus", 0, 2, False, "Str+2:[NL]Unit is granted STR +2."),
    _stat("MagBonus", "MagBonus", 6, 2, False, "Mag+2:[NL]Unit is granted MAG +2."),
    _stat("SklBonus", "SklBonus", 1, 2, False, "Skl+2:[NL]Unit is granted SKL +2."),
    _stat("SpdBonus", "SpdBonus", 2, 2, False, "Spd+2:[NL]Unit is granted SPD +2."),
    _stat("LckBonus", "LukBonus", 5, 2, False, "Luck+2:[NL]Unit is granted LUCK +2."),
    _stat("DefBonus", "DefBonus", 3, 2, False, "Def+2:[NL]Unit is granted DEF +2."),
    _stat("ResBonus", "ResBonus", 4, 2, False, "Res+2:[NL]Unit is granted RES +2."),
    _stat("DefiantStr", "DefiantStr", 0, 7, True, "Defiant Str:[NL]STR +7 if HP < 25%."),
    _stat("DefiantMag", "DefiantMag", 6, 7, True, "Defiant Mag:[NL]MAG +7 if HP < 25%."),
    _stat("DefiantSkl", "DefiantSkl", 1, 7, True, "Defiant Skl:[NL]SKL +7 if HP < 25%."),
    _stat("DefiantSpd", "DefiantSpd", 2, 7, True, "Defiant Spd:[NL]SPD +7 if HP < 25%."),
    _stat("DefiantLck", "DefiantLck", 5, 7, True, "Defiant Luck:[NL]LUCK +7 if HP < 25%."),
    _stat("DefiantDef", "DefiantDef", 3, 7, True, "Defiant Def:[NL]DEF +7 if HP < 25%."),
    _stat("DefiantRes", "DefiantRes", 4, 7, True, "Defiant Res:[NL]RES +7 if HP < 25%."),
    Skill("DefiantCrit", "battle", "DefiantCrit", "Defiant Crit:[NL]Crit Rate +50%,[NL]if HP < 25%.",
          code=f"if {_LOW} attacker->battleCritRate += 50;"),
    Skill("DefiantAvoid", "battle", "DefiantAvoid", "Defiant Avoid:[NL]Avoid Rate +30%,[NL]if HP < 25%.",
          code=f"if {_LOW} attacker->battleAvoidRate += 30;"),
    Skill("BlowDarting", "battle", "BlowDarting", "Darting Blow:[NL]If unit initiates combat,[NL]grants +6 AS during combat.",
          code=f"if {_FIRST} attacker->battleSpeed += 6;"),
    Skill("BlowDeath", "battle", "BlowDeath", "Death Blow:[NL]If unit initiates combat,[NL]grants +6 STR during combat.",
          code=f"if ({_FIRST} && !{_MAGIC % 'attacker'}) attacker->battleAttack += 6;"),
    Skill("BlowArmored", "battle", "BlowArmored", "Armored Blow:[NL]If unit initiates combat,[NL]grants +6 DEF during combat.",
          code=f"if ({_FIRST} && !{_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    Skill("BlowWarding", "battle", "BlowWarding", "Warding Blow:[NL]If unit initiates combat,[NL]grants +6 RES during combat.",
          code=f"if ({_FIRST} && {_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    Skill("Wrath", "battle", "Wrath", "Wrath:[NL]If current HP is < 50%[NL]of max, +20 Crit Rate.",
          code=f"if {_HALF} attacker->battleCritRate += 20;"),
    Skill("Vantage", "order", "Vantage", "Vantage:[NL]When unit is defender while[NL]their HP is < 50%, attack first."),
    Skill("Desperation", "order", "Desperation",
          "Desperation:[NL]When unit attacks with HP < 50%,[NL]its follow-up comes at once."),
    # lot 2: skills that trigger on a hit, Skill % of the time (C-SkillSys, SkillEffects/BattleDamage/*Skills.c)
    Skill("Luna", "proc", "Luna", "Luna:[NL]Negates enemy defense.[NL](Skill % activation).",
          code="if (!magic && SkillProcFem(attacker, SKILL_FEM_Luna)) {\n"
               "            *defense = 0;\n            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_PIERCE;\n        }"),
    Skill("Corona", "proc", "Corona", "Corona:[NL]Negates enemy resistance.[NL](Skill % activation).",
          code="if (magic && SkillProcFem(attacker, SKILL_FEM_Corona)) {\n"
               "            *defense = 0;\n            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_PIERCE;\n        }"),
    Skill("Sol", "proc", "Sol", "Sol:[NL]Restores damage dealt as HP.[NL](Skill % activation).",
          code="if (SkillProcFem(attacker, SKILL_FEM_Sol))\n            sHitDrainFem = TRUE;"),
    Skill("Aether", "proc", "Aether", "Aether:[NL]Negates 80% of enemy defenses[NL]and absorbs HP (Skill %).",
          code="if (SkillProcFem(attacker, SKILL_FEM_Aether)) {\n"
               "            *defense -= *defense * 80 / 100;\n            sHitDrainFem = TRUE;\n        }"),
    Skill("Ignis", "proc", "Ignis", "Ignis:[NL]Adds DEF/2 (RES/2 with magic)[NL]to attack (Skill % activation).",
          code="if (SkillProcFem(attacker, SKILL_FEM_Ignis))\n"
               "            *attack += (magic ? attacker->unit.res : attacker->unit.def) / 2;"),
    Skill("Colossus", "proc", "Colossus", "Colossus:[NL]Damage +200%.[NL](Skill % activation).",
          after="if (!(gBattleHitIterator->attributes & (BATTLE_HIT_ATTR_CRIT | BATTLE_HIT_ATTR_SILENCER))"
                " && SkillProcFem(attacker, SKILL_FEM_Colossus)) {\n"
                "            gBattleStats.damage *= 3;\n"
                "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_CRIT;\n        }"),
    Skill("Pavise", "proc", "Pavise", "Pavise:[NL]Nullifies a physical attack.[NL](Skill % activation).",
          code="if (!magic && SkillProcFem(defender, SKILL_FEM_Pavise))\n"
               "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_GREATSHLD;"),
    Skill("Adept", "hits", "Adept", "Adept:[NL]Attacks one more time[NL]when HP is full.",
          code="if (SkillTesterFem(&unit->unit, SKILL_FEM_Adept) && unit->hpInitial == unit->unit.maxHP)\n"
               "            more += 1;"),
    Skill("Astra", "hits", "Astra", "Astra:[NL]Unit attacks 5 times but damage[NL]is halved. (SPD % activation).",
          code="if (unit == &gBattleActor && SkillProcRateFem(unit, SKILL_FEM_Astra, unit->unit.spd)) {\n"
               "            sAstraFem = TRUE;\n            more += 4;\n        }",
          after="if (sAstraFem && attacker == &gBattleActor)\n            gBattleStats.damage /= 2;"),
    Skill("Aegis", "proc", "Aegis", "Aegis:[NL]Nullifies a magic attack.[NL](Skill % activation).",
          code="if (magic && SkillProcFem(defender, SKILL_FEM_Aegis))\n"
               "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_GREATSHLD;"),
)

# The game's class abilities, shown as skills: their engine stays the game's (texts written for FE8's own rules).
GAME_SKILLS: tuple[Skill, ...] = (
    Skill("Canto", "game", "Canto", "Canto:[NL]Unit can move again after[NL]acting.", game="UNIT_CATTRIBUTES(unit) & CA_CANTO"),
    Skill("Steal", "game", "Steal", "Steal:[NL]Unit can use the[NL]Steal command.", game="UNIT_CATTRIBUTES(unit) & CA_STEAL"),
    Skill("LockTouch", "game", "LockTouch", "Lock Touch:[NL]Opens doors and chests[NL]without keys.",
          game="UNIT_CATTRIBUTES(unit) & CA_THIEF"),
    Skill("Dance", "game", "Dance", "Dance:[NL]Unit can use the[NL]Dance command.",
          game="UNIT_CATTRIBUTES(unit) & (CA_DANCE | CA_PLAY)"),
    # the convoy: the supply class, or the route's lord (SupplyUsability, bmmenu.c)
    Skill("Supply", "game", "Supply", "Supply:[NL]Unit can use the[NL]Supply command.",
          game="(UNIT_CATTRIBUTES(unit) & CA_SUPPLY) || unit->pCharacterData->number =="
               " (gPlaySt.chapterModeIndex == CHAPTER_MODE_EPHRAIM ? CHARACTER_EPHRAIM : CHARACTER_EIRIKA)"),
    Skill("Crit", "game", "Crit", "Crit +15:[NL]Crit rate +15%.", game="UNIT_CATTRIBUTES(unit) & CA_CRITBONUS"),
    Skill("Lethality", "game", "Lethality", "Lethality:[NL]May kill in one hit.[NL](Skill % activation)",
          game="UNIT_CATTRIBUTES(unit) & CA_ASSASSIN"),
    Skill("Summon", "game", "Summon", "Summon:[NL]Unit can call a phantom[NL]to fight.",
          game="UNIT_CATTRIBUTES(unit) & CA_SUMMON"),
    Skill("SureShot", "game", "SureShot", "Sure Strike:[NL]Sure hit, damage +50%.[NL](Level % activation)",
          game="unit->pClassData->number == CLASS_SNIPER || unit->pClassData->number == CLASS_SNIPER_F"),
    Skill("Pierce", "game", "Luna", "Pierce:[NL]Ignores enemy defense.[NL](Level % activation)",
          game="unit->pClassData->number == CLASS_WYVERN_KNIGHT || unit->pClassData->number == CLASS_WYVERN_KNIGHT_F"),
    Skill("GreatShield", "game", "GreatShield", "Great Shield:[NL]Nullifies an attack.[NL](Level % activation)",
          game="unit->pClassData->number == CLASS_GENERAL || unit->pClassData->number == CLASS_GENERAL_F"),
    # effective against monsters (IsUnitEffectiveAgainst, bmitem.c); the Skill System's class skill for Bishops
    Skill("Slayer", "game", "Slayer", "Slayer:[NL]Deals effective damage[NL]to monsters.",
          game="unit->pClassData->number == CLASS_BISHOP || unit->pClassData->number == CLASS_BISHOP_F"),
)

BY_ID = {s.id: s for s in CATALOGUE + GAME_SKILLS}
LABEL = "Skills"
# page 1 (ticket 171): the labels of Talk and Lead, the help of Lead (Talk's is the game's, MSG_56A), Lead's "--"
PAGE_TEXTS = ("Talk", "Lead", "Leadership. No effect[LF]\nfor now.", "[DashedLine][DashedLine]")
MAGIC_SKILLS = frozenset(s.id for s in CATALOGUE if s.stat == 6)


def catalogue() -> list[dict]:
    """What FE Maker offers on the sheets (names and descriptions are UI strings: skill.<id>, skill.<id>Hint); Magic
    skills only with the Strength / Magic split."""
    return ([{"id": s.id, "kind": s.kind, "magic": s.id in MAGIC_SKILLS} for s in CATALOGUE]
            + [{"id": sid, "kind": "game", "magic": False} for sid in ASSIGNABLE])


# The game skills in FE Maker's words: the abilities (gamedata.ABILITIES) or the classes that give them
GAME_SOURCES = {"Canto": (["canto"], []), "Steal": (["steal"], []), "LockTouch": (["thiefSkills"], []),
                "Dance": (["dance", "play"], []), "Supply": (["supply"], []), "Crit": (["critBonus"], []),
                "Lethality": (["lethality"], []), "Summon": (["summon"], []),
                "SureShot": ([], ["CLASS_SNIPER", "CLASS_SNIPER_F"]),
                "Pierce": ([], ["CLASS_WYVERN_KNIGHT", "CLASS_WYVERN_KNIGHT_F"]),
                "GreatShield": ([], ["CLASS_GENERAL", "CLASS_GENERAL_F"]),
                "Slayer": ([], ["CLASS_BISHOP", "CLASS_BISHOP_F"])}
GAME_CHARACTERS = {"Supply": ["CHARACTER_EIRIKA", "CHARACTER_EPHRAIM"]}   # the routes' lords


# Batch 4: the game abilities a sheet can give to anyone, by their class attribute: the game tests them everywhere
# (AI included) with UNIT_CATTRIBUTES, which then adds SkillAttributesFem (docs/competences.md)
ASSIGNABLE = {"Canto": "CA_CANTO", "Steal": "CA_STEAL", "LockTouch": "CA_THIEF", "Crit": "CA_CRITBONUS",
              "Lethality": "CA_ASSASSIN"}


def given(characters: list[dict], classes: list[dict], extra=()) -> set[str]:
    """The skills the sheets give (own lists, learned by level) and the events' (extra)."""
    ids = {sid for record in [*characters, *classes] for sid in record.get("skills") or []}
    ids |= {entry.get("skill") for record in [*characters, *classes] for entry in record.get("learnedSkills") or []}
    return ids | set(extra)


def game_catalogue() -> list[dict]:
    return [{"id": s.id, "abilities": GAME_SOURCES[s.id][0], "classes": GAME_SOURCES[s.id][1],
             "characters": GAME_CHARACTERS.get(s.id, [])} for s in GAME_SKILLS]


def event_skills(sources) -> set[str]:
    """The skills the chapters' events give or take (GiveSkill / RemoveSkill, rendered as SKILL_FEM_<id>)."""
    return {m for source in sources for m in re.findall(r"SKILL_FEM_(\w+)\)", source)}


def used(characters: list[dict], classes: list[dict], magic_split: bool, extra=()) -> list[Skill]:
    """The project's skills in catalogue order, then every game skill (numbers 1 to N); `extra`: event_skills."""
    ids = given(characters, classes, extra)
    chosen = [s for s in CATALOGUE if s.id in ids and (magic_split or s.id not in MAGIC_SKILLS)]
    return (chosen + list(GAME_SKILLS))[:MAX_SKILLS]


# --- icons --------------------------------------------------------------------------------------------------------

def _cache() -> Path:
    return config_dir() / "cskillsys" / COMMIT[:12] / "SkillIcon"


def icon_png(skill_id: str) -> bytes:
    """The skill's icon (16 x 16, indexed in the game's icon palette), downloaded once from C-SkillSys."""
    return icon_path(skill_id).read_bytes()


def icon_path(skill_id: str) -> Path:
    """The cached icon file, downloaded first if needed."""
    skill = BY_ID.get(skill_id)
    if skill is None:
        raise SkillError("unknownSkill")
    return _download(ICON_URL.format(skill.icon), _cache() / f"{skill.icon}.png")


def box_png() -> bytes:
    """The box behind a triggered skill's name in battle (Huichelaar's ProcDisplayTiles, Skill System, CC0)."""
    return _download(BOX_URL, config_dir() / "skillsystem" / SS_COMMIT[:12] / "ProcDisplayTiles.png").read_bytes()


def _download(url: str, path: Path) -> Path:
    if path.is_file():
        return path
    from ..ferepo import _ssl_context
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            data = response.read(64 * 1024)
    except (urllib.error.URLError, OSError) as e:
        raise SkillError("iconsUnreachable") from e
    if not data.startswith(b"\x89PNG"):
        raise SkillError("iconsUnreachable")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# --- texts --------------------------------------------------------------------------------------------------------

def add_texts(data, skills: list[Skill]) -> dict[str, int]:
    """The in-game texts (DecompData.add_texts, before its files are written): "Skills", page 1's labels, then each
    skill's help."""
    numbers = data.add_texts(LABEL, *PAGE_TEXTS, *(s.text.replace("[NL]", "[LF]\n") for s in skills))
    skill_numbers = numbers[1 + len(PAGE_TEXTS):]
    return {"label": numbers[0], "talk": numbers[1], "lead": numbers[2], "leadHelp": numbers[3],
            "leadValue": numbers[4], **{s.id: n for s, n in zip(skills, skill_numbers)}}


# --- C ------------------------------------------------------------------------------------------------------------

ICON_TABLE = "0x02028900"   # end of fontgrp.c's debug print buffer, unused by the game (StanHash's FREE-RAM-SPACE doc)
ICON_TABLE_SIZE = 0x120     # entries of 4 bytes (agbcc aligns the 2-byte struct): up to 0x02028D80, before gNumberStr
GETTERS = {0: "GetUnitPower", 1: "GetUnitSkill", 2: "GetUnitSpeed", 3: "GetUnitDefense", 4: "GetUnitResistance",
           5: "GetUnitLuck", 6: "GetUnitMagicFem"}


def _read(files: dict, decomp_dir: Path, rel: str) -> str:
    return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")


def _replace(text: str, old: str, new: str, rel: str) -> str:
    if text.count(old) != 1:
        raise SkillError(f"Skills: {rel} does not match this version of the decomp ({old.strip()[:60]})")
    return text.replace(old, new, 1)


def _table(decomp_dir: Path, records: list[dict], numbers: dict[str, int], header: str, new_prefix: str) -> str:
    """One row per table entry with skills (entries numbered as strmag.py does: constant, new entry, free entry)."""
    constants = strmag._numbers(decomp_dir, header)
    rows = {}
    for record in records:
        n = strmag._number(record.get("id", ""), constants, new_prefix)
        sids = [numbers[s] for s in record.get("skills") or [] if s in numbers][:MAX_PER_SHEET]
        if n is not None and 0 <= n < 0x100 and sids:
            rows[n] = f"    [0x{n:02X}] = {{ {', '.join(str(s) for s in sids + [0] * (MAX_PER_SHEET - len(sids)))} }},"
    return "\n".join(row for _, row in sorted(rows.items()))


def _learn_table(decomp_dir: Path, records: list[dict], numbers: dict[str, int], header: str, new_prefix: str) -> str:
    """Batch 3: one row per entry whose sheet learns skills by level: { level, skill } pairs."""
    constants = strmag._numbers(decomp_dir, header)
    rows = {}
    for record in records:
        n = strmag._number(record.get("id", ""), constants, new_prefix)
        pairs = [(int(e.get("level") or 0), numbers[e["skill"]]) for e in record.get("learnedSkills") or []
                 if e.get("skill") in numbers and 0 < int(e.get("level") or 0) <= 40][:LEARN_PER_SHEET]
        if n is not None and 0 <= n < 0x100 and pairs:
            cells = ", ".join(f"{{ {lv}, {sk} }}" for lv, sk in pairs + [(0, 0)] * (LEARN_PER_SHEET - len(pairs)))
            rows[n] = f"    [0x{n:02X}] = {{ {cells} }},"
    return "\n".join(row for _, row in sorted(rows.items()))


def apply(decomp_dir: Path, files: dict, characters: list[dict], classes: list[dict], texts: dict[str, int],
          magic_split: bool, extra=()) -> dict:
    """The skills into the overlay `files` (after strmag.apply). `texts`: add_texts's numbers; `extra`: event_skills."""
    skills = used(characters, classes, magic_split, extra)
    numbers = {s.id: i + 1 for i, s in enumerate(skills)}
    defines = "".join(f"#define SKILL_FEM_{s.id} {numbers[s.id]}\n" for s in skills)

    # bmunit.h: numbers and functions; the game abilities given by sheets or events added to UNIT_CATTRIBUTES
    rel = "include/bmunit.h"
    header = _read(files, decomp_dir, rel)
    abilities = [sid for sid in ASSIGNABLE if sid in given(characters, classes, extra)]
    if abilities:
        attributes = "#define UNIT_CATTRIBUTES(aUnit) ((aUnit)->pCharacterData->attributes | (aUnit)->pClassData->attributes)\n"
        header = _replace(header, attributes, (
            "int SkillAttributesFem(struct Unit* unit); /* FE Maker: game abilities given as skills */\n"
            "#define UNIT_CATTRIBUTES(aUnit) ((aUnit)->pCharacterData->attributes | (aUnit)->pClassData->attributes"
            " | SkillAttributesFem(aUnit))\n"), rel)
    files[rel] = _replace(header, "\n#endif // GUARD_BM_UNIT_H", (
        "\n/* FE Maker: skills (docs/competences.md, from C-SkillSys) */\n#define SKILLS_FEM 1\n" + defines +
        f"#define SKILL_COUNT_FEM {len(skills)}\n"
        f"extern const u8 gCharacterSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        f"extern const u8 gClassSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        "int SkillTesterFem(struct Unit* unit, int skill);\nint SkillStatBonusFem(struct Unit* unit, int stat);\n"
        f"#define LEARNED_MAX_FEM {LEARNED_MAX}\n#define LEARNED_CHARACTERS_FEM 0x{LEARNED_CHARACTERS:X}\n"
        f"#define LEARNED_SKILLS_FEM ((u8 (*)[LEARNED_MAX_FEM]) {LEARNED_TABLE})\n"
        "void LearnSkillFem(struct Unit* unit, int skill);\nvoid ForgetSkillFem(struct Unit* unit, int skill);\n"
        "void LearnLevelSkillsFem(struct Unit* unit);\nvoid LearnedPopupsClearFem(void);\n"
        "void LearnedPopupsFem(void* proc);\n"
        + "".join(f"int {GETTERS[k]}BaseFem(struct Unit* unit);\n" for k in sorted({s.stat for s in skills if s.kind == "stat"}))
        +
        "\n#endif // GUARD_BM_UNIT_H"), rel)

    # bmunit.c: tables, tester, stat bonuses, getters
    rel = "src/bmunit.c"
    unit = _read(files, decomp_dir, rel)
    char_rows = _table(decomp_dir, characters, numbers, "characters.h", "CHARACTER_NEW_")
    class_rows = _table(decomp_dir, classes, numbers, "classes.h", "CLASS_NEW_")
    bonuses = {k: [] for k in GETTERS}
    for s in skills:
        if s.kind == "stat":
            cond = "defiant && " if s.defiant else ""
            bonuses[s.stat].append(f"        if ({cond}SkillTesterFem(unit, SKILL_FEM_{s.id}))\n"
                                   f"            bonus += {s.value};\n")
    cases = "".join(f"    case {k}:\n{''.join(lines)}        break;\n" for k, lines in bonuses.items() if lines)
    unit += ("\n/* FE Maker: skills of characters and classes, by their numbers (docs/competences.md) */\n"
             f"const u8 gCharacterSkillsFem[0x100][{MAX_PER_SHEET}] = {{\n{char_rows}\n}};\n\n"
             f"const u8 gClassSkillsFem[0x100][{MAX_PER_SHEET}] = {{\n{class_rows}\n}};\n\n"
             "/* C-SkillSys's SkillTester, on the character's and the class's lists */\n"
             "int SkillTesterFem(struct Unit* unit, int skill)\n{\n"
             "    const u8* list = gCharacterSkillsFem[unit->pCharacterData->number];\n\n"
             "    if (list[0] == skill || list[1] == skill || list[2] == skill)\n        return TRUE;\n"
             "    list = gClassSkillsFem[unit->pClassData->number];\n"
             "    if (list[0] == skill || list[1] == skill || list[2] == skill)\n        return TRUE;\n"
             "    if (unit->pCharacterData->number >= LEARNED_CHARACTERS_FEM)\n        return FALSE;\n"
             "    list = LEARNED_SKILLS_FEM[unit->pCharacterData->number];\n"
             "    return list[0] == skill || list[1] == skill || list[2] == skill || list[3] == skill;\n}\n\n"
             "/* C-SkillSys's status getters (UnitStatusGetter): a stat's skill bonus; 0 Str, 1 Skl, 2 Spd, 3 Def, 4 Res,"
             " 5 Lck, 6 Mag */\n"
             "int SkillStatBonusFem(struct Unit* unit, int stat)\n{\n    int bonus = 0;\n"
             "    int defiant = unit->curHP * 4 < GetUnitMaxHp(unit);\n\n"
             f"    switch (stat) {{\n{cases}    }}\n    (void) defiant;\n    return bonus;\n}}\n")
    if abilities:   # batch 4: on the lists only (SkillTesterFem), never through UNIT_CATTRIBUTES itself
        unit += ("\n/* Batch 4: the class attributes of the game abilities the unit has as skills */\n"
                 "int SkillAttributesFem(struct Unit* unit)\n{\n    int attributes = 0;\n\n"
                 + "".join(f"    if (SkillTesterFem(unit, SKILL_FEM_{sid}))\n        attributes |= {ASSIGNABLE[sid]};\n"
                           for sid in abilities)
                 + "    return attributes;\n}\n")
    for k, name in GETTERS.items():   # only the stats a skill raises: their getter adds the bonus to the game's value
        if not bonuses[k]:
            continue
        head = f"int {name}(struct Unit* unit) {{"
        prefix = "inline " if f"inline {head}" in unit else ""
        unit = _replace(unit, prefix + head, (
            f"{prefix}{head}\n    return {name}BaseFem(unit) + SkillStatBonusFem(unit, {k});\n}}\n\n"
            f"int {name}BaseFem(struct Unit* unit) {{"), rel)
    files[rel] = unit

    # bmbattle.c: battle skills after the game's own computations, and the order of the rounds
    rel = "src/bmbattle.c"
    battle = _read(files, decomp_dir, rel)
    lines = "".join(f"    if (SkillTesterFem(&attacker->unit, SKILL_FEM_{s.id}))\n        {s.code}\n"
                    for s in skills if s.kind == "battle")
    end = "    ComputeBattleUnitStatusBonuses(attacker);\n}\n"
    battle = _replace(battle, "void ComputeBattleUnitStats(struct BattleUnit* attacker, struct BattleUnit* defender) {", (
        "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n"
        "static void ApplyBattleSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender)\n{\n"
        f"{lines}    (void) defender;\n}}\n\n"
        "void ComputeBattleUnitStats(struct BattleUnit* attacker, struct BattleUnit* defender) {"), rel)
    battle = _replace(battle, end, end.replace("}\n", "    ApplyBattleSkillsFem(attacker, defender);\n}\n"), rel)
    # the triggered skills to show in battle (banim-main.c), cleared for each battle
    marker = "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n"
    battle = _replace(battle, marker, (
        f"#define sSkillShownFem ((vu8*) {SHOWN_SKILLS})\n#define SKILL_SHOWN_SIZE_FEM 0x{SHOWN_SIZE:X}\n\n" + marker), rel)
    if any(s.kind == "order" for s in skills):
        battle = _battle_order(battle, numbers, rel)
    if any(s.kind in ("proc", "hits") for s in skills):
        battle = _hit_skills(battle, [s for s in skills if s.kind in ("proc", "hits")], rel)
    battle = _replace(battle, "void BattleUnwind(void) {\n    ClearBattleHits();\n",
                      "void BattleUnwind(void) {\n    ClearBattleHits();\n"
                      "    CpuFill16(0, (void*) sSkillShownFem, SKILL_SHOWN_SIZE_FEM);\n", rel)
    files[rel] = battle

    # icons: after the game's, their lookup table in free RAM
    rel = "data/data_item_icon.s"
    sheet = _read(files, decomp_dir, rel)
    base = sheet.count('.incbin "graphics/item_icon/item_icon_') - sheet.count("item_icon_palette.agbpal")
    icons = "".join(f"\t.global item_icon_skill_fem_{s.id}\nitem_icon_skill_fem_{s.id}:\n"
                    f"\t.incbin \"graphics/item_icon/item_icon_skill_fem_{s.id}.4bpp\"\n" for s in skills)
    box = ("\t.align 2\n\t.global gSkillBoxFem\ngSkillBoxFem:\n"
           "\t.incbin \"graphics/item_icon/skill_box_fem.4bpp\"\n")
    files[rel] = _replace(sheet, "\t.global item_icon_palette\n", icons + box + "\t.global item_icon_palette\n", rel)
    for s in skills:
        files[f"graphics/item_icon/item_icon_skill_fem_{s.id}.png"] = icon_png(s.id)
    files["graphics/item_icon/skill_box_fem.png"] = box_png()
    files.update(_skill_name_in_battle(decomp_dir, files, skills, texts, base))
    rel = "src/icon.c"
    icon = _read(files, decomp_dir, rel)
    icon = _replace(icon, "EWRAM_DATA static struct IconStruct DrawnIconLookupTable[MAX_ICON_COUNT] = {0};\n", (
        "/* FE Maker (skills): the game's 224 icons and the skills' after them, their table in free RAM; the old one stays,"
        " unused, so that EWRAM keeps its layout */\n"
        "EWRAM_DATA struct IconStruct DrawnIconLookupTableOldFem[MAX_ICON_COUNT] = {0};\n"
        f"#define DrawnIconLookupTable ((struct IconStruct*) {ICON_TABLE})\n"
        f"#define ICON_TABLE_SIZE_FEM 0x{ICON_TABLE_SIZE:X}\n"), rel)
    icon = _replace(icon, "CpuFill16(0, &DrawnIconLookupTable, sizeof(DrawnIconLookupTable));",
                    "CpuFill16(0, DrawnIconLookupTable, ICON_TABLE_SIZE_FEM * sizeof(struct IconStruct));", rel)
    files[rel] = icon

    files.update(_status_screen(decomp_dir, files, skills, texts, base, magic_split))
    files.update(_learned(decomp_dir, files, _learn_table(decomp_dir, characters, numbers, "characters.h", "CHARACTER_NEW_"),
                          _learn_table(decomp_dir, classes, numbers, "classes.h", "CLASS_NEW_"), skills, numbers,
                          texts, base))
    return files


DRAIN_FLAG = "0x02028D80"   # one byte after the icon table, in the same free RAM: Sol or Aether triggered on this hit
ASTRA_FLAG = "0x02028D81"   # the next one: Astra triggered in this battle (the attacker's hits are halved)
# then the triggered skills to show, 2 bytes per hit (the actor's, the target's), and the last round shown: 0x02028D82-91
SHOWN_SKILLS = "0x02028D82"
SHOWN_SIZE = 0x10


def _hit_skills(battle: str, procs: list[Skill], rel: str) -> str:
    """Skills that trigger on a hit, Skill % of the time (C-SkillSys's CheckBattleSkillActivate, never in the forecast):
    before the damage (defense, attack, Pavise and Aegis as the game's Great Shield, Luna and Corona as its Pierce),
    after the critical roll (Colossus, shown as a critical hit), and the HP drain of Sol and Aether, as Nosferatu's."""
    hits = [s for s in procs if s.kind == "hits"]
    before = "".join(f"    {{\n        {s.code}\n    }}\n" for s in procs if s.kind == "proc" and s.code)
    more = "".join(f"    {{\n        {s.code}\n    }}\n" for s in hits)
    after = "".join(f"    {{\n        {s.after}\n    }}\n" for s in procs if s.after)
    battle = _replace(battle, "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n", f"""\
/* FE Maker: skills that trigger on a hit (C-SkillSys: SkillActRate.c, SkillEffects/BattleDamage) */
#define sHitDrainFem (*(vu8*) {DRAIN_FLAG})
#define sAstraFem (*(vu8*) {ASTRA_FLAG})

static int SkillProcRateFem(struct BattleUnit* unit, int skill, int rate)
{{
    if (gBattleStats.config & BATTLE_CONFIG_SIMULATE)
        return FALSE;
    if (!SkillTesterFem(&unit->unit, skill))
        return FALSE;
    if (!BattleRoll2RN(rate, FALSE))
        return FALSE;
    /* its name is shown with this hit (2 bytes per hit: the actor's skill, the target's) */
    if (gBattleHitIterator < gBattleHitArray + BATTLE_HIT_MAX)
        sSkillShownFem[(gBattleHitIterator - gBattleHitArray) * 2 + (unit == &gBattleTarget)] = skill;
    return TRUE;
}}

static int SkillProcFem(struct BattleUnit* unit, int skill)
{{
    return SkillProcRateFem(unit, skill, unit->unit.skl);
}}

/* Adept and Astra (C-SkillSys, BattleOrder.c, GetBattleUnitHitCount): hits added to a round */
static int HitCountSkillsFem(struct BattleUnit* unit)
{{
    int more = 0;

{more}    return more;
}}

static void ApplyHitSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender, short* attack, short* defense)
{{
    int magic = attacker->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE);

{before}    (void) magic; (void) attack; (void) defense;
}}

static void ApplyHitSkillsAfterFem(struct BattleUnit* attacker, struct BattleUnit* defender)
{{
{after}    (void) defender;
}}

/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */
""", rel)
    battle = _replace(battle, "    gBattleStats.damage = 0;\n\n    BattleCheckSureShot(attacker);\n",
                      "    gBattleStats.damage = 0;\n    sHitDrainFem = FALSE;\n\n    BattleCheckSureShot(attacker);\n", rel)
    battle = _replace(battle, "        defense = 0;\n\n    gBattleStats.damage = attack - defense;\n",
                      "        defense = 0;\n\n    ApplyHitSkillsFem(attacker, defender, &attack, &defense);\n\n"
                      "    gBattleStats.damage = attack - defense;\n", rel)
    cap = ("    if (gBattleStats.damage > BATTLE_MAX_DAMAGE)\n        gBattleStats.damage = BATTLE_MAX_DAMAGE;\n\n"
           "    if (gBattleStats.damage < 0)\n        gBattleStats.damage = 0;\n\n    BattleCheckPetrify(")
    battle = _replace(battle, cap, "    ApplyHitSkillsAfterFem(attacker, defender);\n\n" + cap, rel)
    drain = ("        if (GetItemWeaponEffect(attacker->weapon) == WPN_EFFECT_HPDRAIN) {\n"
             "            if (attacker->unit.maxHP < (attacker->unit.curHP + gBattleStats.damage))\n"
             "                attacker->unit.curHP = attacker->unit.maxHP;\n"
             "            else\n"
             "                attacker->unit.curHP += gBattleStats.damage;\n\n"
             "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_HPSTEAL;\n"
             "        }\n")
    if hits:
        # extra hits: the game keeps 7 entries (6 hits and the end), in RAM at a fixed place: a round stops when full
        battle = _replace(battle, "    result <<= BattleCheckBraveEffect(attacker);\n\n    return result;\n",
                          "    result <<= BattleCheckBraveEffect(attacker);\n    result += HitCountSkillsFem(attacker);\n\n"
                          "    return result;\n", rel)
        battle = _replace(battle, "    for (i = 0; i < count; ++i) {\n        gBattleHitIterator->attributes |= attrs;\n",
                          "    for (i = 0; i < count && gBattleHitIterator < gBattleHitArray + BATTLE_HIT_MAX - 1; ++i) {\n"
                          "        gBattleHitIterator->attributes |= attrs;\n", rel)
        battle = _replace(battle, "void BattleUnwind(void) {\n    ClearBattleHits();\n",
                          "void BattleUnwind(void) {\n    ClearBattleHits();\n    sAstraFem = FALSE;\n", rel)
    return _replace(battle, drain, drain.replace(
        "        if (GetItemWeaponEffect(attacker->weapon) == WPN_EFFECT_HPDRAIN) {\n",
        "        if (GetItemWeaponEffect(attacker->weapon) == WPN_EFFECT_HPDRAIN\n"
        "            || (sHitDrainFem && gBattleStats.damage > 0)) { /* FE Maker: Sol, Aether */\n"), rel)


def _skill_name_in_battle(decomp_dir: Path, files: dict, skills: list[Skill], texts: dict[str, int], base: int) -> dict:
    """The triggered skill's name and icon under the unit's name plate, in battle animations: Huichelaar's
    SkillProcDisplay from the Skill System (CC0), started where the game plays its own skill effects (C07)."""
    out = {}
    numbers = {s.id: i + 1 for i, s in enumerate(skills)}
    icons = ", ".join(str(base + i) for i in range(len(skills)))
    descs = ", ".join(str(texts[s.id]) for s in skills)
    game = {flag: numbers.get(sid, 0) for flag, sid in (("SURE_SHOT", "SureShot"), ("PIERCE", "Pierce"),
                                                        ("GREAT_SHIELD", "GreatShield"))}
    rel = "src/banim-ekrgauge.c"
    gauge = _read(files, decomp_dir, rel)
    # the HP bar's buffer leaves the last 4 tiles of its 2 rows alone: the skill icon is there (KeepProcSkillIcon.s)
    out[rel] = _replace(gauge, "        RegisterDataMove((void *)gUnk_Banim_02016E48, (void *)0x06013000, 0x800);\n",
                        "        RegisterDataMove((void *)gUnk_Banim_02016E48, (void *)0x06013000, 0x380);"
                        " /* FE Maker: skill icon (Huichelaar) */\n"
                        "        RegisterDataMove((void *)gUnk_Banim_02017248, (void *)0x06013400, 0x380);\n", rel)
    # in bmbattle.c, whose constants the linker keeps (banim-main.c's .rodata is discarded)
    rel = "src/bmbattle.c"
    battle = _read(files, decomp_dir, rel)
    out[rel] = battle + f'''
#include "anime.h"
#include "ekrbattle.h"
#include "fontgrp.h"
#include "bmlib.h"
#include "icon.h"
#include "functions.h"
#include "hardware.h"

/* FE Maker: the triggered skill's name and icon in battle (Huichelaar's SkillProcDisplay, Skill System, CC0) */
#define sSkillRoundFem (*(vu8*) ({SHOWN_SKILLS} + 2 * BATTLE_HIT_MAX))
#define SKILL_NAME_TIME_FEM 120
#define SKILL_NAME_WIDTH_FEM 8

extern struct Font* gActiveFont;
extern const u8 gSkillBoxFem[];

static const u16 sSkillIconFem[SKILL_COUNT_FEM + 1] = {{ 0, {icons} }};
static const u16 sSkillTextFem[SKILL_COUNT_FEM + 1] = {{ 0, {descs} }};

struct SkillNameProcFem {{
    PROC_HEADER;
    u8 skill;
    u8 right;
    u8 timer;
    struct Text text;
}};

static void SkillNameInitFem(struct SkillNameProcFem* proc)
{{
    struct Font font;
    struct Font* active = gActiveFont;
    char name[0x20];
    u16 palette[0x10];
    const char* str = GetStringFromIndex(sSkillTextFem[proc->skill]);
    int i;

    for (i = 0; str[i] && str[i] != ':' && i < 0x1F; i++)   /* the help text up to its colon */
        name[i] = str[i];
    name[i] = 0;

    Copy2dChr(item_icon_tiles + sSkillIconFem[proc->skill] * 0x80, (void*) 0x6013380, 2, 2);

    CpuCopy16(PAL_BG(2), palette, sizeof(palette));   /* the font loads its palette there: the gauge's is kept */
    InitTextFont(&font, (void*) 0x6000020, 1, 2);
    CpuCopy16(palette, PAL_BG(2), sizeof(palette));
    SetTextDrawNoClear();   /* the glyphs replace the box's pixels */
    InitText(&proc->text, SKILL_NAME_WIDTH_FEM);
    Text_SetCursor(&proc->text, GetStringTextCenteredPos(SKILL_NAME_WIDTH_FEM * 8, name));
    CpuFastCopy(gSkillBoxFem, (void*) 0x6000020, SKILL_NAME_WIDTH_FEM * 64);
    Text_DrawString(&proc->text, name);
    SetTextFont(active);
    proc->timer = 0;
}}

/* the name slides in under the name plate, stays, slides back; the icon follows its end */
static void SkillNameLoopFem(struct SkillNameProcFem* proc)
{{
    struct Anim icon;
    s16 x;
    int i, end = proc->timer - (SKILL_NAME_TIME_FEM + (SKILL_NAME_WIDTH_FEM + 2));

    proc->timer++;
    if (proc->timer > SKILL_NAME_TIME_FEM + (SKILL_NAME_WIDTH_FEM + 2) * 2) {{
        Proc_Break(proc);
        return;
    }}
    if (proc->timer <= SKILL_NAME_WIDTH_FEM + 2) {{
        x = proc->timer << 3;
        for (i = 0; i < proc->timer - 2; i++) {{
            if (proc->right) {{
                gBG0TilemapBuffer[0x9D - ((proc->timer - 3) - i)] = 0x3000 | (1 + i * 2);
                gBG0TilemapBuffer[0xBD - ((proc->timer - 3) - i)] = 0x3000 | (2 + i * 2);
            }} else {{
                gBG0TilemapBuffer[0x80 + ((proc->timer - 3) - i)] = 0x2000 | ((SKILL_NAME_WIDTH_FEM * 2 - 1) - i * 2);
                gBG0TilemapBuffer[0xA0 + ((proc->timer - 3) - i)] = 0x2000 | ((SKILL_NAME_WIDTH_FEM * 2) - i * 2);
            }}
        }}
        BG_EnableSyncByMask(BG0_SYNC_BIT);
    }} else if (end > 0) {{
        x = ((SKILL_NAME_WIDTH_FEM + 2) - end) << 3;
        if (proc->right) {{
            gBG0TilemapBuffer[(0x9D - SKILL_NAME_WIDTH_FEM) + end] = 0x3080;
            gBG0TilemapBuffer[(0xBD - SKILL_NAME_WIDTH_FEM) + end] = 0x3080;
            for (i = end; i < SKILL_NAME_WIDTH_FEM; i++) {{
                gBG0TilemapBuffer[(0x9D - SKILL_NAME_WIDTH_FEM) + i + 1] = 0x3000 | (((i - end) * 2) + 1);
                gBG0TilemapBuffer[(0xBD - SKILL_NAME_WIDTH_FEM) + i + 1] = 0x3000 | (((i - end) * 2) + 2);
            }}
        }} else {{
            gBG0TilemapBuffer[(0x80 + SKILL_NAME_WIDTH_FEM) - end] = 0x2080;
            gBG0TilemapBuffer[(0xA0 + SKILL_NAME_WIDTH_FEM) - end] = 0x2080;
            for (i = end; i < SKILL_NAME_WIDTH_FEM; i++) {{
                gBG0TilemapBuffer[(0x80 + SKILL_NAME_WIDTH_FEM) - (i + 1)] =
                    0x2000 | ((SKILL_NAME_WIDTH_FEM * 2) - (((i - end) * 2) + 1));
                gBG0TilemapBuffer[(0xA0 + SKILL_NAME_WIDTH_FEM) - (i + 1)] =
                    0x2000 | ((SKILL_NAME_WIDTH_FEM * 2) - ((i - end) * 2));
            }}
        }}
        BG_EnableSyncByMask(BG0_SYNC_BIT);
    }} else
        x = (SKILL_NAME_WIDTH_FEM + 2) * 8;

    x = proc->right ? 240 - x : x - 16;
    icon.pSpriteData = gUnknown_085B9544;
    icon.oamBase = 0;
    icon.oam2Base = 0xD19C;   /* the item icon palette (OBJ 13), tile 0x19C */
    icon.xPosition = gpProcEkrGauge->unk32 + x;
    icon.yPosition = gpProcEkrGauge->unk3A + 32;
    icon.state2 = 0;
    AnimDisplay(&icon);
}}

static void SkillNameEndFem(struct SkillNameProcFem* proc)
{{
    int i;

    CpuFastFill(0, (void*) 0x6013380, 0x40);
    CpuFastFill(0, (void*) 0x6013780, 0x40);
    CpuFastFill(0, (void*) 0x6000020, SKILL_NAME_WIDTH_FEM * 64);
    for (i = 0; i < SKILL_NAME_WIDTH_FEM; i++) {{
        gBG0TilemapBuffer[0x80 + i] = 0x2080;
        gBG0TilemapBuffer[0xA0 + i] = 0x2080;
        gBG0TilemapBuffer[0x9D - i] = 0x3080;
        gBG0TilemapBuffer[0xBD - i] = 0x3080;
    }}
    BG_EnableSyncByMask(BG0_SYNC_BIT);
}}

static const struct ProcCmd ProcScr_SkillNameFem[] = {{
    PROC_NAME("SkillNameFem"),
    PROC_SET_END_CB(SkillNameEndFem),
    PROC_END_DUPLICATES,
    PROC_SLEEP(1),
    PROC_CALL(SkillNameInitFem),
    PROC_REPEAT(SkillNameLoopFem),
    PROC_END,
}};

/* At C07 (the attack starts), once per round: the attacker's triggered skill, else the defender's, else the game's
   Sure Strike, Pierce or Great Shield */
void StartSkillNameFem(struct Anim* anim)
{{
    struct SkillNameProcFem* proc;
    int round = anim->nextRoundId - 1;
    int pos = GetAnimPosition(anim);
    int actor = (pos == POS_L) == (gpEkrBattleUnitLeft == &gBattleActor);
    int skill, right = pos == POS_R;
    u16 flags;

    if (round < 0 || round >= BATTLE_HIT_MAX || sSkillRoundFem == round + 1 || gpProcEkrGauge == NULL)
        return;
    sSkillRoundFem = round + 1;
    skill = sSkillShownFem[round * 2 + !actor];
    flags = GetRoundFlagByAnim(anim);
    /* the attacker's skill plays the game's skill flash and sound (Sure Strike's), as the Skill System does,
       unless a game effect (Pierce for Luna, Great Shield for Pavise) already plays */
    if (skill && !(flags & (ANIM_ROUND_SURE_SHOT | ANIM_ROUND_PIERCE | ANIM_ROUND_GREAT_SHIELD))
        && gAnimRoundData[round * 2 + pos] != 0xFFFF)
        gAnimRoundData[round * 2 + pos] |= ANIM_ROUND_SURE_SHOT;
    if (skill == 0) {{
        skill = sSkillShownFem[round * 2 + actor];
        right = !right;
    }}
    if (skill == 0) {{
        right = pos == POS_R;
        if (flags & ANIM_ROUND_SURE_SHOT)
            skill = {game["SURE_SHOT"]};
        else if (flags & ANIM_ROUND_PIERCE)
            skill = {game["PIERCE"]};
        else if (flags & ANIM_ROUND_GREAT_SHIELD) {{
            skill = {game["GREAT_SHIELD"]};
            right = !right;
        }}
    }}
    if (skill == 0 || skill > SKILL_COUNT_FEM)
        return;
    proc = Proc_Start(ProcScr_SkillNameFem, gpProcEkrGauge);
    proc->skill = skill;
    proc->right = right;
}}

/* Battles on the map: the icon beside the info box for 30 frames (Huichelaar's SPD_Map, Skill System, CC0) */
#include "mapanim.h"

#define SKILL_ICON_MAP_TIME_FEM 30

struct SkillIconMapProcFem {{
    PROC_HEADER;
    u8 skill;
    u8 left;
    u8 timer;
    u8 x;
    u8 y;
}};

static void SkillIconMapClearFem(struct SkillIconMapProcFem* proc)
{{
    int l = proc->left ? -1 : 1, m = proc->left, i, j;

    for (i = 0; i < 2; i++)
        for (j = 0; j < 3; j++)
            gBG0TilemapBuffer[(proc->y + i + 1) * 0x20 + (proc->x + (10 + m + j) * l)] = 0;
    BG_EnableSyncByMask(BG0_SYNC_BIT);
}}

static void SkillIconMapInitFem(struct SkillIconMapProcFem* proc)
{{
    CpuFastCopy(item_icon_tiles + sSkillIconFem[proc->skill] * 0x80, (void*) 0x6000C00, 0x80);
    ApplyPalettes(item_icon_palette[0], 4, 1);
    proc->timer = 0;
}}

/* the icon opens over 2 frames, stays, closes */
static void SkillIconMapLoopFem(struct SkillIconMapProcFem* proc)
{{
    int i, j, k, offset, l = proc->left ? -1 : 1, m = proc->left;

    proc->timer++;
    SkillIconMapClearFem(proc);
    if (proc->timer >= SKILL_ICON_MAP_TIME_FEM + 3) {{
        Proc_Break(proc);
        return;
    }}
    if (proc->timer == 1 || proc->timer - SKILL_ICON_MAP_TIME_FEM == 2)
        offset = 0;
    else if (proc->timer == 2 || proc->timer - SKILL_ICON_MAP_TIME_FEM == 1)
        offset = 1;
    else
        offset = 2;
    k = offset ? 2 : 1;
    for (i = 0; i < k; i++)
        for (j = 0; j < 2; j++)
            gBG0TilemapBuffer[(proc->y + j + 1) * 0x20 + proc->x + l * (10 + m - i + offset)] = j * 2 - i * l + 0x4061 - m;
}}

static const struct ProcCmd ProcScr_SkillIconMapFem[] = {{
    PROC_NAME("SkillIconMapFem"),
    PROC_SET_END_CB(SkillIconMapClearFem),
    PROC_END_DUPLICATES,
    PROC_YIELD,
    PROC_CALL(SkillIconMapInitFem),
    PROC_REPEAT(SkillIconMapLoopFem),
    PROC_END,
}};

/* Before each round of a map battle: the hit attacker's triggered skill, else the defender's, else the game's */
void StartSkillIconMapFem(ProcPtr parent)
{{
    struct BattleHit* hit = gManimSt.pCurrentRound;
    struct MAInfoFrameProc* box = Proc_Find(ProcScr_MapBattleInfoBox);
    struct SkillIconMapProcFem* proc;
    int round = hit - gBattleHitArray;
    int target = !!(hit->info & BATTLE_HIT_INFO_RETALIATION);   /* the hit's attacker: 0 the actor, 1 the target */
    int owner = target, skill;

    if (box == NULL || round < 0 || round >= BATTLE_HIT_MAX)
        return;
    skill = sSkillShownFem[round * 2 + owner];
    if (skill == 0) {{
        owner = !target;
        skill = sSkillShownFem[round * 2 + owner];
    }}
    if (skill == 0) {{
        owner = target;
        if (hit->attributes & BATTLE_HIT_ATTR_SURESHOT)
            skill = {game["SURE_SHOT"]};
        else if (hit->attributes & BATTLE_HIT_ATTR_PIERCE)
            skill = {game["PIERCE"]};
        else if (hit->attributes & BATTLE_HIT_ATTR_GREATSHLD) {{
            skill = {game["GREAT_SHIELD"]};
            owner = !target;
        }}
    }}
    if (skill == 0 || skill > SKILL_COUNT_FEM)
        return;
    proc = Proc_Start(ProcScr_SkillIconMapFem, parent);
    proc->skill = skill;
    proc->left = owner;   /* the actor's skill on the right, the target's on the left */
    proc->x = box->x;
    proc->y = box->y;
}}
'''
    rel = "src/mapanim.c"
    out[rel] = _replace(_read(files, decomp_dir, rel),
                        "    MapAnim_AdvanceBattleRound();\n    gManimSt.specialProcScr",
                        "    StartSkillIconMapFem(proc); /* FE Maker: skills.py, in bmbattle.c */\n"
                        "    MapAnim_AdvanceBattleRound();\n    gManimSt.specialProcScr", rel)
    out[rel] = _replace(out[rel], "void MapAnim_AdvanceBattleRound(void)\n{",
                        "void StartSkillIconMapFem(ProcPtr parent);\n\nvoid MapAnim_AdvanceBattleRound(void)\n{", rel)
    rel = "src/banim-main.c"
    main = _replace(_read(files, decomp_dir, rel), "void BattleAIS_ExecCommands(void)\n{",
                    "void StartSkillNameFem(struct Anim* anim); /* FE Maker: skills.py, in bmbattle.c */\n\n"
                    "void BattleAIS_ExecCommands(void)\n{", rel)
    out[rel] = _replace(main, "                case 0x07:\n",
                        "                case 0x07:\n                    if (GetAISLayerId(anim) == 0)\n"
                        "                        StartSkillNameFem(anim); /* FE Maker */\n", rel)
    return out


def _battle_order(battle: str, numbers: dict[str, int], rel: str) -> str:
    """Vantage and Desperation (C-SkillSys, BattleOrder.c): the defender strikes first, the attacker's follow-up comes
    at once."""
    start = battle.index("void BattleUnwind(void) {")
    end = battle.index("void BattleGetBattleUnitOrder(", start)
    vantage = ("SkillTesterFem(&gBattleTarget.unit, SKILL_FEM_Vantage) && gBattleTarget.weapon"
               " && gBattleTarget.hpInitial * 2 < gBattleTarget.unit.maxHP") if "Vantage" in numbers else "FALSE"
    desperation = ("SkillTesterFem(&gBattleActor.unit, SKILL_FEM_Desperation)"
                   " && gBattleActor.hpInitial * 2 < gBattleActor.unit.maxHP") if "Desperation" in numbers else "FALSE"
    return battle[:start] + f"""void BattleUnwind(void) {{
    ClearBattleHits();

    /* FE Maker: Vantage and Desperation (skills, from C-SkillSys's BattleOrder.c) */
    do {{
        struct BattleUnit* attacker;
        struct BattleUnit* defender;
        int vantage = {vantage};
        int desperation = {desperation};
        int followed = FALSE;

        BattleGetBattleUnitOrder(&attacker, &defender);

        gBattleHitIterator->info |= BATTLE_HIT_INFO_BEGIN;

        if (vantage) {{
            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_RETALIATE;

            if (BattleGenerateRoundHits(defender, attacker))
                break;
        }}

        if (BattleGenerateRoundHits(attacker, defender))
            break;

        if (desperation && BattleGetFollowUpOrder(&attacker, &defender) && attacker == &gBattleActor) {{
            gBattleHitIterator->attributes = BATTLE_HIT_ATTR_FOLLOWUP;

            if (BattleGenerateRoundHits(attacker, defender))
                break;

            followed = TRUE;
        }}

        BattleGetBattleUnitOrder(&attacker, &defender);

        if (!vantage) {{
            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_RETALIATE;

            if (BattleGenerateRoundHits(defender, attacker))
                break;
        }}

        if (!followed && BattleGetFollowUpOrder(&attacker, &defender)) {{
            gBattleHitIterator->attributes = BATTLE_HIT_ATTR_FOLLOWUP;

            BattleGenerateRoundHits(attacker, defender);
        }}
    }} while (FALSE);

    gBattleHitIterator->info |= BATTLE_HIT_INFO_END;
}}

""" + battle[end:]


LEARNED_POPUPS = "0x02028DA0"   # after the shown skills, same free RAM: count, then (unit index, skill) x 4
LEARNED_NAME = "0x02028DB0"     # the popup's skill name (0x20 bytes), then its 11 instructions (0x58): up to 0x02028E28


def _learned(decomp_dir: Path, files: dict, char_learn: str, class_learn: str, skills: list[Skill],
             numbers: dict[str, int], texts: dict[str, int], base: int) -> dict:
    """Learned skills (batch 3): LearnSkillFem / ForgetSkillFem in bmunit.c, the table cleared for a new game, and
    saved per save slot like Magic (after its blocks): the save time, then the table."""
    out = {}
    icons = ", ".join(str(base + i) for i in range(len(skills)))
    descs = ", ".join(str(texts[s.id]) for s in skills)
    rel = "src/bmunit.c"
    out[rel] = _read(files, decomp_dir, rel) + """
/* FE Maker: learned skills (batch 3, docs/competences.md; C-SkillSys's LearnSkill.c): 4 per character, the oldest
   forgotten for a 5th; player units only, as C-SkillSys */
void LearnSkillFem(struct Unit* unit, int skill)
{
    u8* list;
    int i;

    if (UNIT_FACTION(unit) != FACTION_BLUE || unit->pCharacterData->number >= LEARNED_CHARACTERS_FEM
        || skill <= 0 || skill > SKILL_COUNT_FEM || SkillTesterFem(unit, skill))
        return;
    list = LEARNED_SKILLS_FEM[unit->pCharacterData->number];
    for (i = 0; i < LEARNED_MAX_FEM; i++)
        if (list[i] == 0) {
            list[i] = skill;
            return;
        }
    for (i = 0; i < LEARNED_MAX_FEM - 1; i++)
        list[i] = list[i + 1];
    list[LEARNED_MAX_FEM - 1] = skill;
}

void ForgetSkillFem(struct Unit* unit, int skill)
{
    u8* list;
    int i, j;

    if (unit->pCharacterData->number >= LEARNED_CHARACTERS_FEM)
        return;
    list = LEARNED_SKILLS_FEM[unit->pCharacterData->number];
    for (i = 0; i < LEARNED_MAX_FEM; i++)
        if (list[i] == skill) {
            for (j = i; j < LEARNED_MAX_FEM - 1; j++)
                list[j] = list[j + 1];
            list[LEARNED_MAX_FEM - 1] = 0;
            return;
        }
}
"""
    out[rel] += f"""
/* Batch 3: "learns X at level N" of the character and class sheets (as C-SkillSys's SkillTable-person.c / -job.c),
   at a level up and at a promotion (level 1 of the new class) */
static const u8 sCharacterLearnFem[0x100][{LEARN_PER_SHEET}][2] = {{
{char_learn}
}};

static const u8 sClassLearnFem[0x100][{LEARN_PER_SHEET}][2] = {{
{class_learn}
}};

static void LearnShownFem(struct Unit* unit, int skill);

void LearnLevelSkillsFem(struct Unit* unit)
{{
    int i;

    for (i = 0; i < {LEARN_PER_SHEET}; i++) {{
        if (sCharacterLearnFem[unit->pCharacterData->number][i][0] == unit->level)
            LearnShownFem(unit, sCharacterLearnFem[unit->pCharacterData->number][i][1]);
        if (sClassLearnFem[unit->pClassData->number][i][0] == unit->level)
            LearnShownFem(unit, sClassLearnFem[unit->pClassData->number][i][1]);
    }}
}}

/* The skills learned in a battle, shown after it in a popup ("Eirika learned Luna."), with their icon */
#include "popup.h"
#include "proc.h"
#include "fontgrp.h"
#include "functions.h"

#define sLearnedCountFem (*(vu8*) {LEARNED_POPUPS})
#define sLearnedQueueFem ((vu8*) {LEARNED_POPUPS} + 2)
#define sLearnedNameFem ((char*) {LEARNED_NAME})
#define sLearnedInstFem ((struct PopupInstruction*) ({LEARNED_NAME} + 0x20))

static const u16 sLearnedIconFem[SKILL_COUNT_FEM + 1] = {{ 0, {icons} }};
static const u16 sLearnedTextFem[SKILL_COUNT_FEM + 1] = {{ 0, {descs} }};
static const char sLearnedWordFem[] = " learned ";
static const char sLearnedDotFem[] = ".";

void LearnedPopupsClearFem(void)
{{
    sLearnedCountFem = 0;
}}

static void LearnShownFem(struct Unit* unit, int skill)
{{
    if (SkillTesterFem(unit, skill))
        return;
    LearnSkillFem(unit, skill);
    if (SkillTesterFem(unit, skill) && sLearnedCountFem < 4) {{
        sLearnedQueueFem[2 * sLearnedCountFem] = unit->index;
        sLearnedQueueFem[2 * sLearnedCountFem + 1] = skill;
        sLearnedCountFem++;
    }}
}}

static void LearnedInstFem(int i, int opcode, u32 data)
{{
    sLearnedInstFem[i].opcode = opcode;
    sLearnedInstFem[i].data = data;
}}

/* PROC_REPEAT: one popup per learned skill (each blocks the proc), then on */
void LearnedPopupsFem(ProcPtr proc)
{{
    const char* str;
    int i, skill;

    if (sLearnedCountFem == 0 || sLearnedCountFem > 4) {{
        sLearnedCountFem = 0;
        Proc_Break(proc);
        return;
    }}
    skill = sLearnedQueueFem[1];
    SetPopupUnit(GetUnit(sLearnedQueueFem[0]));
    for (i = 1; i < sLearnedCountFem; i++) {{
        sLearnedQueueFem[2 * i - 2] = sLearnedQueueFem[2 * i];
        sLearnedQueueFem[2 * i - 1] = sLearnedQueueFem[2 * i + 1];
    }}
    sLearnedCountFem--;
    if (skill <= 0 || skill > SKILL_COUNT_FEM)
        return;
    str = GetStringFromIndex(sLearnedTextFem[skill]);
    for (i = 0; str[i] && str[i] != ':' && i < 0x1F; i++)   /* the help text up to its colon */
        sLearnedNameFem[i] = str[i];
    sLearnedNameFem[i] = 0;
    SetPopupItem(0x1000 + sLearnedIconFem[skill]);   /* the icon: see POPUP_OP_WTYPE_ICON in popup.c */
    LearnedInstFem(0, POPUP_OP_SOUND, 0x5A);
    LearnedInstFem(1, POPUP_OP_COLOR, TEXT_COLOR_SYSTEM_BLUE);
    LearnedInstFem(2, POPUP_OP_UNIT_NAME, 0);
    LearnedInstFem(3, POPUP_OP_COLOR, TEXT_COLOR_SYSTEM_WHITE);
    LearnedInstFem(4, POPUP_OP_STR, (u32) sLearnedWordFem);
    LearnedInstFem(5, POPUP_OP_WTYPE_ICON, 0);
    LearnedInstFem(6, POPUP_OP_COLOR, TEXT_COLOR_SYSTEM_BLUE);
    LearnedInstFem(7, POPUP_OP_STR, (u32) sLearnedNameFem);
    LearnedInstFem(8, POPUP_OP_COLOR, TEXT_COLOR_SYSTEM_WHITE);
    LearnedInstFem(9, POPUP_OP_STR, (u32) sLearnedDotFem);
    LearnedInstFem(10, POPUP_OP_END, 0);
    NewPopup_Simple(sLearnedInstFem, 0x60, 0x0, proc);
}}
"""
    rel = "src/bmbattle.c"
    battle = _read(files, decomp_dir, rel)
    battle = _replace(battle, "    unit->level = bu->unit.level;\n",
                      "    if (bu->unit.level != unit->level) { /* FE Maker: skills learned at this level */\n"
                      "        unit->level = bu->unit.level;\n        LearnLevelSkillsFem(unit);\n    }\n", rel)
    promotion = "    unit->level = 1;\n    unit->exp   = 0;\n"
    if battle.count(promotion) != 2:
        raise SkillError(f"Skills: {rel} does not match this version of the decomp (promotions)")
    battle = battle.replace(promotion, promotion + "    LearnLevelSkillsFem(unit); /* FE Maker: learned at promotion */\n")
    battle = _replace(battle, "void BattleApplyGameStateUpdates(void) {\n",
                      "void BattleApplyGameStateUpdates(void) {\n    LearnedPopupsClearFem(); /* FE Maker */\n", rel)
    battle = _replace(battle, "    PROC_CALL(UpdateActorFromBattle),\n    PROC_END\n",
                      "    PROC_CALL(LearnedPopupsClearFem),\n    PROC_CALL(UpdateActorFromBattle),\n"
                      "    PROC_REPEAT(LearnedPopupsFem), /* FE Maker: skills learned */\n    PROC_END\n", rel)
    out[rel] = battle
    rel = "src/bmmind.c"
    mind = _read(files, decomp_dir, rel)
    mind = _replace(mind, "PROC_LABEL(1),\n    PROC_CALL_2(BATTLE_HandleItemDrop),\n",
                    "PROC_LABEL(1),\n    PROC_REPEAT(LearnedPopupsFem), /* FE Maker: skills learned */\n"
                    "    PROC_CALL_2(BATTLE_HandleItemDrop),\n", rel)
    out[rel] = _replace(mind, "PROC_LABEL(1),\n    PROC_CALL(BATTLE_HandleArenaDeathsMaybe),\n",
                        "PROC_LABEL(1),\n    PROC_REPEAT(LearnedPopupsFem), /* FE Maker: skills learned in the arena */\n"
                        "    PROC_CALL(BATTLE_HandleArenaDeathsMaybe),\n", rel)
    rel = "src/uiarena.c"
    out[rel] = _replace(_read(files, decomp_dir, rel), "    UpdateUnitFromBattle(gArenaState.playerUnit, &gBattleActor);\n",
                        "    LearnedPopupsClearFem(); /* FE Maker */\n"
                        "    UpdateUnitFromBattle(gArenaState.playerUnit, &gBattleActor);\n", rel)
    rel = "src/popup.c"
    out[rel] = _replace(_read(files, decomp_dir, rel), """        case POPUP_OP_WTYPE_ICON:
            proc->iconX = len;
            proc->iconId = gPopupItem + 0x70;
            LoadIconPalette(1, proc->iconPalId);
""", """        case POPUP_OP_WTYPE_ICON:
            proc->iconX = len;
            if (gPopupItem >= 0x1000) { /* FE Maker: a skill's icon (0x1000 + its icon), item palette */
                proc->iconId = gPopupItem - 0x1000;
                LoadIconPalette(0, proc->iconPalId);
                len += 0x10;
                break;
            }
            proc->iconId = gPopupItem + 0x70;
            LoadIconPalette(1, proc->iconPalId);
""", rel)
    out[rel] += """
/* Batch 3: events give or take a skill: slot 1 the character, slot 2 the skill, slot 3 1 to give, 0 to take */
#include "event.h"

void FemSkillEvent(void)
{
    struct Unit* unit = GetUnitStructFromEventParameter(gEventSlots[1]);

    if (!unit)
        return;
    if (gEventSlots[3])
        LearnSkillFem(unit, gEventSlots[2]);
    else
        ForgetSkillFem(unit, gEventSlots[2]);
}
"""
    rel = "include/eventscript.h"
    out[rel] = _read(files, decomp_dir, rel).rstrip("\n") + (
        "\n\n/* FE Maker: skills for the events' GiveSkill / RemoveSkill */\n#define SKILLS_FEM_EVENTS 1\n"
        + "".join(f"#define SKILL_FEM_{s.id} {numbers[s.id]}\n" for s in skills) + "void FemSkillEvent(void);\n")
    rel = "src/bmio.c"
    out[rel] = _replace(_read(files, decomp_dir, rel), "    CpuFill16(0, &gPlaySt, sizeof(gPlaySt));\n",
                        "    CpuFill16(0, &gPlaySt, sizeof(gPlaySt));\n"
                        "    CpuFill16(0, LEARNED_SKILLS_FEM, LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM); /* FE Maker */\n",
                        rel)
    rel = "src/bmsave.c"
    text = _read(files, decomp_dir, rel)
    save = f"""/* FE Maker: learned skills, per save slot after Magic's blocks (docs/competences.md, batch 3): the save time,
   then the table; a save without them (made before) has none */
#define LEARNED_SAVE_FEM(slot) ((u8 *) CART_SRAM + SRAM_OFFSET_XMAP + 0x{LEARNED_SAVE:X} \\
    + (slot) * (4 + LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM))

static void WriteLearnedFem(int slot)
{{
    u32 time = gPlaySt.time_saved;

    WriteAndVerifySramFast(&time, LEARNED_SAVE_FEM(slot), 4);
    WriteAndVerifySramFast(LEARNED_SKILLS_FEM, LEARNED_SAVE_FEM(slot) + 4, LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM);
}}

static void ReadLearnedFem(int slot)
{{
    u32 time;

    ReadSramFast(LEARNED_SAVE_FEM(slot), &time, 4);
    if (time == gPlaySt.time_saved)
        ReadSramFast(LEARNED_SAVE_FEM(slot) + 4, LEARNED_SKILLS_FEM, LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM);
    else
        CpuFill16(0, LEARNED_SKILLS_FEM, LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM);
}}

static void CopyLearnedFem(int src, int dest)
{{
    u8 buf[4 + LEARNED_CHARACTERS_FEM * LEARNED_MAX_FEM];

    ReadSramFast(LEARNED_SAVE_FEM(src), buf, sizeof(buf));
    WriteAndVerifySramFast(buf, LEARNED_SAVE_FEM(dest), sizeof(buf));
}}

"""
    game_write = ("    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n"
                  "        WriteGameSavePackedUnit(&gUnitArrayBlue[i], &dest->units[i]);\n")
    game_read = "    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n        LoadSavedUnit(src->units + i, &gUnitArrayBlue[i]);\n"
    suspend_write = ("    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n"
                     "        EncodeSuspendSavePackedUnit(&gUnitArrayBlue[i], buf++);\n")
    suspend_read = "    SetBonusContentClaimFlags(LoadSavedBonusClaimFlags(gPlaySt.gameSaveSlot));\n"
    copy = "    WriteAndVerifySramFast(gGenericBuffer, dest, sizeof(struct GameSaveBlock));\n"
    for old, new in (
            ("void CopyGameSave(int index_src, int index_dest)\n{", save + "void CopyGameSave(int index_src, int index_dest)\n{"),
            (copy, copy + "    CopyLearnedFem(index_src, index_dest);\n"),
            (game_write, game_write + "    WriteLearnedFem(slot);\n"),
            (game_read, game_read + "    ReadLearnedFem(slot);\n"),
            (suspend_write, "    WriteLearnedFem(slot);\n" + suspend_write),
            (suspend_read, suspend_read + "    ReadLearnedFem(slot + gSuspendSaveIdOffset);\n")):
        text = _replace(text, old, new, rel)
    out[rel] = text
    return out


def _status_screen(decomp_dir: Path, files: dict, skills: list[Skill], texts: dict[str, int], base: int,
                   magic_split: bool) -> dict:
    """Page 1 laid out as the Skill System's MSS (ticket 171, docs/competences.md).

    Left: Str (Mag) Skl Spd Lck Def Res, then Mov. Right: Con, Aid, Cond, Lead ("---" for now), Talk (who the unit can
    talk to, as C-SkillSys's GetTalkee), "Skills" and 2 rows of 3 icons. The affinity icon goes beside the name; Trv and
    the battles / wins / losses line leave the page. R help: rebuilt for the whole page."""
    out = {}
    mov_row = 15 if magic_split else 13
    rel = "include/statscreen.h"
    header = _read(files, decomp_dir, rel)
    out[rel] = _replace(header, "    STATSCREEN_TEXT_BWL, // 34\n",
                        "    STATSCREEN_TEXT_BWL, // 34\n    STATSCREEN_TEXT_SKILLS_FEM, // FE Maker: \"Skills\"\n", rel)
    rel = "src/statscreen.c"
    text = _read(files, decomp_dir, rel)
    text = _replace(text, "    { gStatScreen.text + STATSCREEN_TEXT_BWL,        16 },\n",
                    "    { gStatScreen.text + STATSCREEN_TEXT_BWL,        16 },\n"
                    "    { gStatScreen.text + STATSCREEN_TEXT_SKILLS_FEM, 4 },\n", rel)
    # the battles / wins / losses line leaves (the growth rates' HP line, before it, stays: it takes Mov's row)
    text = _replace(text, "\n    if (!stats)\n        return;\n",
                    "\n    return; /* FE Maker: page 1 has no room for this line (ticket 171) */\n\n"
                    "    if (!stats)\n        return;\n", rel)

    # labels: Mov to the left column, the right column one row up, Lead and Talk in Trv's and Affin's texts
    labels = {"MOVLABEL": (1, mov_row, "&gMid_Mov"), "CONLABEL": (9, 1, "&gMid_Con"), "AIDLABEL": (9, 3, "&gMid_Aid"),
              "STATUS": (9, 5, "&gMid_Cnd"), "AFFINLABEL": (9, 7, "&sMidLeadFem"),
              "RESCUENAME": (9, 9, "&sMidTalkFem")}
    for name, (x, y, mid) in labels.items():
        pattern = re.compile(rf"    \{{ gStatScreen\.text \+ STATSCREEN_TEXT_{name}, +"
                             r"gUiTmScratchA \+ TILEMAP_INDEX\(\d+, \d+\), +TEXT_COLOR_SYSTEM_GOLD, 0, &gMid_\w+ \},\n")
        line = (f"    {{ gStatScreen.text + STATSCREEN_TEXT_{name}, gUiTmScratchA + TILEMAP_INDEX({x}, {y}), "
                f"TEXT_COLOR_SYSTEM_GOLD, 0, {mid} }},\n")
        text, count = pattern.subn(line, text, count=1)
        if not count:
            raise SkillError(f"Skills: {rel} does not match (label {name})")
    text = _replace(text, "struct SSTextDispInfo const sPage0TextInfo[] =\n", (
        "/* FE Maker (ticket 171): page 1's Lead and Talk */\n"
        f"static const u32 sMidLeadFem = {texts['lead']};\nstatic const u32 sMidTalkFem = {texts['talk']};\n\n"
        "struct SSTextDispInfo const sPage0TextInfo[] =\n"), rel)

    # values
    growths = "#ifdef STATSCREEN_BGPAL_GROWTHS_FEM\n    if (!gStatScreen.growthsFem) /* HP's growth takes this row */\n#endif\n"
    pairs = [
        ("    DrawStatWithBar(6, 13, 1,\n", growths + f"    DrawStatWithBar(6, 5, {mov_row},\n"),
        ("    DrawStatWithBar(7, 13, 3,\n", "    DrawStatWithBar(7, 13, 1,\n"),
        ("gUiTmScratchA + TILEMAP_INDEX(13, 5), TEXT_COLOR_SYSTEM_BLUE,",
         "gUiTmScratchA + TILEMAP_INDEX(13, 3), TEXT_COLOR_SYSTEM_BLUE,"),
        ("    DrawIcon(gUiTmScratchA + TILEMAP_INDEX(14, 5),\n", "    DrawIcon(gUiTmScratchA + TILEMAP_INDEX(14, 3),\n"),
        ("    Text_InsertDrawString(\n        &gStatScreen.text[STATSCREEN_TEXT_RESCUENAME],\n"
         "        24, TEXT_COLOR_SYSTEM_BLUE,\n        GetUnitRescueName(gStatScreen.unit));\n",
         "    DisplayLeadTalkFem(); /* FE Maker (ticket 171): in the place of Trv */\n"),
        ("                gUiTmScratchA + TILEMAP_INDEX(16, 11),\n", "                gUiTmScratchA + TILEMAP_INDEX(16, 5),\n"),
        ("    DrawIcon(\n        gUiTmScratchA + TILEMAP_INDEX(12, 9),\n        GetUnitAffinityIcon(gStatScreen.unit),\n"
         "        OAM2_PAL(STATSCREEN_BGPAL_EXTICONS));\n",
         "    /* FE Maker (ticket 171): the affinity icon is beside the name */\n"),
        # the affinity beside the name (the name is centred in 6 tiles of its 7: the 7th is free)
        ("        TEXT_COLOR_SYSTEM_WHITE, namexoff, 0, namestr);\n",
         "        TEXT_COLOR_SYSTEM_WHITE, namexoff, 0, namestr);\n\n"
         "    /* FE Maker (ticket 171): the affinity beside the name */\n"
         "    DrawIcon(gBG0TilemapBuffer + TILEMAP_INDEX(9, 10), GetUnitAffinityIcon(gStatScreen.unit),\n"
         "        OAM2_PAL(STATSCREEN_BGPAL_EXTICONS));\n"),
    ]
    for old, new in pairs:
        text = _replace(text, old, new, rel)

    game = [s for s in skills if s.kind == "game"]
    icons = ", ".join(str(base + i) for i in range(len(skills)))
    descs = ", ".join(str(texts[s.id]) for s in skills)
    game_lines = "".join(f"    if (({s.game}) && !SkillTesterFem(unit, SKILL_FEM_{s.id}))\n"
                         f"        list[count++] = SKILL_FEM_{s.id};\n" for s in game)
    size = 2 * MAX_PER_SHEET + LEARNED_MAX + len(game)
    helpers = f"""#include "constants/characters.h"
#include "chapterdata.h"
#include "event.h"
#include "eventinfo.h"
#include "eventscript.h"

/* FE Maker: skills on page 1 (docs/competences.md; layout of the Skill System's MSS, ticket 171) */
static const u16 sSkillIconFem[SKILL_COUNT_FEM + 1] = {{ 0, {icons} }};
static const u16 sSkillTextFem[SKILL_COUNT_FEM + 1] = {{ 0, {descs} }};

static int GetUnitSkillListFem(struct Unit* unit, u8* list)
{{
    const u8* own = gCharacterSkillsFem[unit->pCharacterData->number];
    int i, count = 0;

    for (i = 0; i < {MAX_PER_SHEET}; i++)
        if (own[i])
            list[count++] = own[i];
    own = gClassSkillsFem[unit->pClassData->number];
    for (i = 0; i < {MAX_PER_SHEET}; i++)
        if (own[i])
            list[count++] = own[i];
    if (unit->pCharacterData->number < LEARNED_CHARACTERS_FEM) {{
        own = LEARNED_SKILLS_FEM[unit->pCharacterData->number];
        for (i = 0; i < LEARNED_MAX_FEM; i++)
            if (own[i])
                list[count++] = own[i];
    }}
{game_lines}    return count;
}}

static void DisplaySkillsFem(void)
{{
    u8 list[{size}];
    int i, count = GetUnitSkillListFem(gStatScreen.unit, list);
    const char* label = GetStringFromIndex({texts["label"]});

    if (count == 0)
        return;
    ClearText(&gStatScreen.text[STATSCREEN_TEXT_SKILLS_FEM]);
    PutDrawText(&gStatScreen.text[STATSCREEN_TEXT_SKILLS_FEM], gUiTmScratchA + TILEMAP_INDEX(9, 11),
        TEXT_COLOR_SYSTEM_GOLD, 0, 0, label);
    for (i = 0; i < count && i < {MAX_SHOWN}; i++)
        DrawIcon(gUiTmScratchA + TILEMAP_INDEX(9 + (i % 3) * 3, 13 + (i / 3) * 2), sSkillIconFem[list[i]], 0x4000);
}}

/* Talk: who the unit can talk to now, a talk event of the chapter first, then a support (C-SkillSys's GetTalkee,
   Kernel/Wizardry/Core/StatScreen/DrawUnitPage/Source/Util.c) */
int EvCheck03_CHAR(struct EventInfo* info);
extern struct EventListCmdInfo CONST_DATA gEventListCmdInfoTable[];

static bool UnitOnMapFem(struct Unit* unit)
{{
    return unit && unit->pCharacterData && !(unit->state & (US_HIDDEN | US_UNAVAILABLE));
}}

static int GetTalkeeFem(struct Unit* unit)
{{
    const EventListScr* list = GetChapterEventDataPointer(gPlaySt.chapterIndex)->characterBasedEvents;
    struct EventInfo info;
    int i, cmd;

    for (; list && (cmd = list[0] & 0xFFFF) != EVT_LIST_CMD_END; list += gEventListCmdInfoTable[cmd].length)
    {{
        if (cmd != EVT_LIST_CMD_CHAR || CheckFlag(list[0] >> 16))
            continue;
        info.listScript = list;
        info.pidA = UNIT_CHAR_ID(unit);
        info.pidB = ((const u8*) list)[9];
        if (EvCheck03_CHAR(&info) && UnitOnMapFem(GetUnitFromCharId(info.pidB)))
            return info.pidB;
    }}
    for (i = 0; i < GetUnitSupporterCount(unit); i++)
    {{
        struct Unit* other = GetUnitSupporterUnit(unit, i);

        if (UnitOnMapFem(other) && CanUnitSupportNow(unit, i))
            return UNIT_CHAR_ID(other);
    }}
    return 0;
}}

static void DisplayLeadTalkFem(void)
{{
    int talkee = GetTalkeeFem(gStatScreen.unit);

    Text_InsertDrawString(&gStatScreen.text[STATSCREEN_TEXT_AFFINLABEL], 24, TEXT_COLOR_SYSTEM_BLUE,
        GetStringFromIndex({texts["leadValue"]})); /* Lead: none yet */
    Text_InsertDrawString(&gStatScreen.text[STATSCREEN_TEXT_RESCUENAME], 24, TEXT_COLOR_SYSTEM_BLUE,
        GetStringFromIndex(talkee ? UNIT_NAME_ID(GetUnitFromCharId(talkee)) : MSG_536));
}}

static void HbPopulate_SkillFem(struct HelpBoxProc* proc)
{{
    u8 list[{size}];

    GetUnitSkillListFem(gStatScreen.unit, list);
    proc->msgId = sSkillTextFem[list[proc->info->msgId]];
}}

static void HbRedirect_SkillFem(struct HelpBoxProc* proc)
{{
    u8 list[{size}];

    if (proc->info->msgId < GetUnitSkillListFem(gStatScreen.unit, list))
        return;
    if (proc->moveKey == DPAD_RIGHT)
        TryRelocateHbLeft(proc);
    else
        TryRelocateHbUp(proc);
}}

"""
    text = _replace(text, "void DisplayPage0(void)\n{", helpers + "void DisplayPage0(void)\n{", rel)
    text = _replace(text, "    DisplayBwl();\n}\n", "    DisplayBwl();\n    DisplaySkillsFem();\n}\n", rel)

    # R help of the whole page, rebuilt
    start = text.index("DECL_INFO gHelpInfo_Ss0Pow =\n")
    end = text.index("// Stat Screen Page 1 (Items & battle stats) (Ss1)")
    text = text[:start] + _help_entries(magic_split) + text[end:]
    text = _replace(text, "    NULL, &sHelpInfo_Class, NULL, &sHelpInfo_Ss0Lck,\n    24, 80,",
                    "    NULL, &sHelpInfo_Class, NULL, &sHelpInfo_Ss0Affinity,\n    24, 80,", rel)
    text = text.replace("DECL_INFO sHelpInfo_Char =\n", "extern DECL_INFO sHelpInfo_Ss0LeadFem;\n" + "".join(
        f"extern DECL_INFO sHelpInfo_SkillFem{i};\n" for i in range(MAX_SHOWN)) + "\nDECL_INFO sHelpInfo_Char =\n", 1)
    out[rel] = text.replace("sHelpInfo_Ss0LeadFem_MSG", str(texts["leadHelp"]))
    return out


def _help_entries(magic_split: bool) -> str:
    """Page 1's R help boxes (ticket 171): up, down, left, right, x, y, message, redirect, populate."""
    left = [("gHelpInfo_Ss0Pow", 102, "MSG_546", "NULL, NULL" if magic_split else "NULL, HbPopulate_SSPower")]
    if magic_split:
        left.append(("sHelpInfo_Ss0MagFem", 102, "MSG_547", ""))
    left += [("sHelpInfo_Ss0Skl", 105, "MSG_548", ""), ("sHelpInfo_Ss0Spd", 102, "MSG_549", ""),
             ("sHelpInfo_Ss0Lck", 102, "MSG_54A", ""), ("sHelpInfo_Ss0Def", 102, "MSG_54B", ""),
             ("sHelpInfo_Ss0Res", 102, "MSG_54C", ""), ("sHelpInfo_Ss0Mov", 102, "MSG_54D", "")]
    right = [("sHelpInfo_Ss0Con", "MSG_54E", ""), ("sHelpInfo_Ss0Aid", "MSG_54F", ""),
             ("sHelpInfo_Ss0Status", "0", "NULL, HbPopulate_SSStatus"), ("sHelpInfo_Ss0LeadFem", "sHelpInfo_Ss0LeadFem_MSG", ""),
             ("sHelpInfo_Ss0Traveler", "MSG_56A", "")]   # Talk keeps Trv's name (the header declares it)
    skill_rows = (120, 136)
    by_y_right = {24 + 16 * j: name for j, (name, _, _) in enumerate(right)}
    by_y_right[104] = by_y_right[120] = "sHelpInfo_SkillFem0"
    by_y_right[136] = "sHelpInfo_SkillFem3"

    def ref(name):
        return f"&{name}" if name else "NULL"

    def left_at(y):   # the left column's entry on that row, or the last one
        return left[min(len(left), (y - 24) // 16 + 1) - 1][0]

    def entry(name, up, down, lft, rgt, x, y, msg, extra):
        tail = f", {extra}" if extra else ""
        return (f"DECL_INFO {name} =\n{{\n    {ref(up)}, {ref(down)}, {ref(lft)}, {ref(rgt)},\n"
                f"    {x}, {y}, {msg}{tail},\n}};\n\n")

    out = ["/* FE Maker (ticket 171): page 1 as the Skill System's MSS */\n"]
    for i, (name, x, msg, extra) in enumerate(left):
        y = 24 + 16 * i
        out.append(entry(name, left[i - 1][0] if i else None, left[i + 1][0] if i + 1 < len(left) else None,
                         "sHelpInfo_Char" if y < 104 else "sHelpInfo_Class", by_y_right.get(y), x, y, msg, extra))
    for j, (name, msg, extra) in enumerate(right):
        y = 24 + 16 * j
        out.append(entry(name, right[j - 1][0] if j else None,
                         right[j + 1][0] if j + 1 < len(right) else "sHelpInfo_SkillFem0",
                         left_at(y), None, 166, y, msg, extra))
    for k in range(MAX_SHOWN):
        row, col = divmod(k, 3)
        y = skill_rows[row]
        out.append(entry(
            f"sHelpInfo_SkillFem{k}", right[-1][0] if row == 0 else f"sHelpInfo_SkillFem{k - 3}",
            f"sHelpInfo_SkillFem{k + 3}" if row == 0 else None,
            left_at(y) if col == 0 else f"sHelpInfo_SkillFem{k - 1}", f"sHelpInfo_SkillFem{k + 1}" if col < 2 else None,
            166 + 24 * col, y, k, "HbRedirect_SkillFem, HbPopulate_SkillFem"))
    out.append(entry("sHelpInfo_Ss0Affinity", None, "sHelpInfo_Class", "sHelpInfo_Char", "sHelpInfo_Ss0Lck",
                     72, 80, "MSG_551", ""))
    return "".join(out)
