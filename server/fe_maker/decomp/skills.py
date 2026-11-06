"""Skills (game option `skills`), ported from C-SkillSys into the decomp (plan: docs/competences.md).

C-SkillSys (https://github.com/MokhaLeee/fe8u-cskillsys-kernel, MIT, Mokha and contributors) is a CHAX for the
original ROM; its effects are written in C on the decomp's names, so they are taken here skill by skill, at the commit
`COMMIT`, into the build overlay. Its license text is kept in licenses/cskillsys-MIT.txt.

- Skills of a character or a class: `skills` on their sheets (3 at most each, as C-SkillSys), in the tables
  gCharacterSkillsFem and gClassSkillsFem; SkillTesterFem(unit, n) tests them. Only the skills the project uses are
  compiled, numbered from 1.
- The game's own class abilities (Canto, Steal, Pierce...) are shown as skills too (GAME_SKILLS), their engine untouched.
- Status screen, page 1: "Skills" and up to 4 icons below Cond, in the place of the battles / wins / losses line
  (layout of the Skill System's MSS, the user's choice); R shows each skill's text.
- Icons: C-SkillSys's (Contents/Gfx/Sources/SkillIcon, already in the game's icon palette), downloaded once and cached,
  never in this repository; they follow the game's 224 icons, whose lookup table moves to free RAM (ICON_TABLE).
- In-game texts: C-SkillSys's (Contents/Texts/Source/texts), its name on the first line.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..config import config_dir
from . import strmag

REPO = "MokhaLeee/fe8u-cskillsys-kernel"
COMMIT = "fb545870458f3c3629cab6cfb2330c3308d2ce6d"
ICON_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Contents/Gfx/Sources/SkillIcon/{{}}.png"
MAX_PER_SHEET = 3
MAX_SHOWN = 4
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
    code: str = ""        # battle skills: C run in ComputeBattleUnitStats (attacker, defender)
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
)

# The game's class abilities, shown as skills: their engine stays the game's (texts written for FE8's own rules).
GAME_SKILLS: tuple[Skill, ...] = (
    Skill("Canto", "game", "Canto", "Canto:[NL]Unit can move again after[NL]acting.", game="UNIT_CATTRIBUTES(unit) & CA_CANTO"),
    Skill("Steal", "game", "Steal", "Steal:[NL]Unit can use the[NL]Steal command.", game="UNIT_CATTRIBUTES(unit) & CA_STEAL"),
    Skill("LockTouch", "game", "LockTouch", "Lock Touch:[NL]Opens doors and chests[NL]without keys.",
          game="UNIT_CATTRIBUTES(unit) & CA_THIEF"),
    Skill("Dance", "game", "Dance", "Dance:[NL]Unit can use the[NL]Dance command.",
          game="UNIT_CATTRIBUTES(unit) & (CA_DANCE | CA_PLAY)"),
    Skill("Supply", "game", "Supply", "Supply:[NL]Unit can use the[NL]Supply command.",
          game="UNIT_CATTRIBUTES(unit) & CA_SUPPLY"),
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
)

BY_ID = {s.id: s for s in CATALOGUE + GAME_SKILLS}
LABEL = "Skills"
MAGIC_SKILLS = frozenset(s.id for s in CATALOGUE if s.stat == 6)


def catalogue() -> list[dict]:
    """What FE Maker offers on the sheets (names and descriptions are UI strings: skill.<id>, skill.<id>Hint); Magic
    skills only with the Strength / Magic split."""
    return [{"id": s.id, "kind": s.kind, "magic": s.id in MAGIC_SKILLS} for s in CATALOGUE]


# The game skills in FE Maker's words: the abilities (gamedata.ABILITIES) or the classes that give them
GAME_SOURCES = {"Canto": (["canto"], []), "Steal": (["steal"], []), "LockTouch": (["thiefSkills"], []),
                "Dance": (["dance", "play"], []), "Supply": (["supply"], []), "Crit": (["critBonus"], []),
                "Lethality": (["lethality"], []), "Summon": (["summon"], []),
                "SureShot": ([], ["CLASS_SNIPER", "CLASS_SNIPER_F"]),
                "Pierce": ([], ["CLASS_WYVERN_KNIGHT", "CLASS_WYVERN_KNIGHT_F"]),
                "GreatShield": ([], ["CLASS_GENERAL", "CLASS_GENERAL_F"])}


def game_catalogue() -> list[dict]:
    return [{"id": s.id, "abilities": GAME_SOURCES[s.id][0], "classes": GAME_SOURCES[s.id][1]} for s in GAME_SKILLS]


def used(characters: list[dict], classes: list[dict], magic_split: bool) -> list[Skill]:
    """The project's skills in catalogue order, then every game skill (numbers 1 to N)."""
    ids = {sid for record in [*characters, *classes] for sid in record.get("skills") or []}
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
    path = _cache() / f"{skill.icon}.png"
    if path.is_file():
        return path
    from ..ferepo import _ssl_context
    request = urllib.request.Request(ICON_URL.format(skill.icon), headers={"User-Agent": "FE-Maker"})
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
    """The in-game texts (DecompData.add_texts, before its files are written): "Skills", then each skill's help."""
    numbers = data.add_texts(LABEL, *(s.text.replace("[NL]", "[LF]\n") for s in skills))
    return {"label": numbers[0], **{s.id: n for s, n in zip(skills, numbers[1:])}}


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


def apply(decomp_dir: Path, files: dict, characters: list[dict], classes: list[dict], texts: dict[str, int],
          magic_split: bool) -> dict:
    """The skills into the overlay `files` (after strmag.apply). `texts`: add_texts's numbers."""
    skills = used(characters, classes, magic_split)
    numbers = {s.id: i + 1 for i, s in enumerate(skills)}
    defines = "".join(f"#define SKILL_FEM_{s.id} {numbers[s.id]}\n" for s in skills)

    # bmunit.h: numbers and functions
    rel = "include/bmunit.h"
    header = _read(files, decomp_dir, rel)
    files[rel] = _replace(header, "\n#endif // GUARD_BM_UNIT_H", (
        "\n/* FE Maker: skills (docs/competences.md, from C-SkillSys) */\n#define SKILLS_FEM 1\n" + defines +
        f"#define SKILL_COUNT_FEM {len(skills)}\n"
        f"extern const u8 gCharacterSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        f"extern const u8 gClassSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        "int SkillTesterFem(struct Unit* unit, int skill);\nint SkillStatBonusFem(struct Unit* unit, int stat);\n"
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
             "    return list[0] == skill || list[1] == skill || list[2] == skill;\n}\n\n"
             "/* C-SkillSys's status getters (UnitStatusGetter): a stat's skill bonus; 0 Str, 1 Skl, 2 Spd, 3 Def, 4 Res,"
             " 5 Lck, 6 Mag */\n"
             "int SkillStatBonusFem(struct Unit* unit, int stat)\n{\n    int bonus = 0;\n"
             "    int defiant = unit->curHP * 4 < GetUnitMaxHp(unit);\n\n"
             f"    switch (stat) {{\n{cases}    }}\n    (void) defiant;\n    return bonus;\n}}\n")
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
    if any(s.kind == "order" for s in skills):
        battle = _battle_order(battle, numbers, rel)
    files[rel] = battle

    # icons: after the game's, their lookup table in free RAM
    rel = "data/data_item_icon.s"
    sheet = _read(files, decomp_dir, rel)
    base = sheet.count('.incbin "graphics/item_icon/item_icon_') - sheet.count("item_icon_palette.agbpal")
    icons = "".join(f"\t.global item_icon_skill_fem_{s.id}\nitem_icon_skill_fem_{s.id}:\n"
                    f"\t.incbin \"graphics/item_icon/item_icon_skill_fem_{s.id}.4bpp\"\n" for s in skills)
    files[rel] = _replace(sheet, "\t.global item_icon_palette\n", icons + "\t.global item_icon_palette\n", rel)
    for s in skills:
        files[f"graphics/item_icon/item_icon_skill_fem_{s.id}.png"] = icon_png(s.id)
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

    files.update(_status_screen(decomp_dir, files, skills, numbers, texts, base))
    return files


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


def _status_screen(decomp_dir: Path, files: dict, skills: list[Skill], numbers: dict[str, int], texts: dict[str, int],
                   base: int) -> dict:
    """Page 1: "Skills" and the icons below Cond (rows 13 and 15, where the battles / wins / losses line was), R help."""
    out = {}
    rel = "include/statscreen.h"
    header = _read(files, decomp_dir, rel)
    out[rel] = _replace(header, "    STATSCREEN_TEXT_BWL, // 34\n",
                        "    STATSCREEN_TEXT_BWL, // 34\n    STATSCREEN_TEXT_SKILLS_FEM, // FE Maker: \"Skills\"\n", rel)
    rel = "src/statscreen.c"
    text = _read(files, decomp_dir, rel)
    text = _replace(text, "    { gStatScreen.text + STATSCREEN_TEXT_BWL,        16 },\n",
                    "    { gStatScreen.text + STATSCREEN_TEXT_BWL,        16 },\n"
                    "    { gStatScreen.text + STATSCREEN_TEXT_SKILLS_FEM, 4 },\n", rel)
    # the battles / wins / losses line gives its place (the growth rates' HP line, before it, stays)
    text = _replace(text, "\n    if (!stats)\n        return;\n",
                    "\n    return; /* FE Maker: the skills take this line's place */\n\n    if (!stats)\n        return;\n", rel)
    game = [s for s in skills if s.kind == "game"]
    icons = ", ".join(str(base + i) for i in range(len(skills)))
    descs = ", ".join(str(texts[s.id]) for s in skills)
    game_lines = "".join(f"    if ({s.game})\n        list[count++] = SKILL_FEM_{s.id};\n" for s in game)
    helpers = f"""/* FE Maker: skills on page 1 (docs/competences.md; layout of the Skill System's MSS) */
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
{game_lines}    return count;
}}

static void DisplaySkillsFem(void)
{{
    u8 list[{2 * MAX_PER_SHEET + len(game)}];
    int i, count = GetUnitSkillListFem(gStatScreen.unit, list);
    const char* label = GetStringFromIndex({texts["label"]});

    if (count == 0)
        return;
    ClearText(&gStatScreen.text[STATSCREEN_TEXT_SKILLS_FEM]);
    PutDrawText(&gStatScreen.text[STATSCREEN_TEXT_SKILLS_FEM], gUiTmScratchA + TILEMAP_INDEX(11, 13),
        TEXT_COLOR_SYSTEM_GOLD, GetStringTextCenteredPos(32, label), 0, label);
    for (i = 0; i < count && i < {MAX_SHOWN}; i++)
        DrawIcon(gUiTmScratchA + TILEMAP_INDEX(9 + i * 2, 15), sSkillIconFem[list[i]], 0x4000);
}}

static void HbPopulate_SkillFem(struct HelpBoxProc* proc)
{{
    u8 list[{2 * MAX_PER_SHEET + len(game)}];

    GetUnitSkillListFem(gStatScreen.unit, list);
    proc->msgId = sSkillTextFem[list[proc->info->msgId]];
}}

static void HbRedirect_SkillFem(struct HelpBoxProc* proc)
{{
    u8 list[{2 * MAX_PER_SHEET + len(game)}];

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
    entries = "".join(
        f"DECL_INFO sHelpInfo_SkillFem{i} =\n{{\n    &sHelpInfo_Ss0Status, NULL, "
        f"{'&sHelpInfo_SkillFem' + str(i - 1) if i else '&sHelpInfo_Ss0Res'}, "
        f"{'&sHelpInfo_SkillFem' + str(i + 1) if i < MAX_SHOWN - 1 else 'NULL'},\n"
        f"    {168 + 16 * i}, 136, {i}, HbRedirect_SkillFem, HbPopulate_SkillFem,\n}};\n\n" for i in range(MAX_SHOWN))
    status = ("DECL_INFO sHelpInfo_Ss0Status =\n{\n    &sHelpInfo_Ss0Affinity, NULL, &sHelpInfo_Ss0Res, NULL,\n"
              "    166, 104, 0, NULL, HbPopulate_SSStatus,\n};\n")
    text = _replace(text, "DECL_INFO sHelpInfo_Ss0Res =\n", "".join(
        f"extern DECL_INFO sHelpInfo_SkillFem{i};\n" for i in range(MAX_SHOWN)) + "\nDECL_INFO sHelpInfo_Ss0Res =\n", rel)
    text = _replace(text, status, (
        status.replace("&sHelpInfo_Ss0Affinity, NULL,", "&sHelpInfo_Ss0Affinity, &sHelpInfo_SkillFem0,") + "\n" + entries),
        rel)
    text = _replace(text, "    &sHelpInfo_Ss0Def, NULL, &sHelpInfo_Class, &sHelpInfo_Ss0Status,\n",
                    "    &sHelpInfo_Ss0Def, &sHelpInfo_SkillFem0, &sHelpInfo_Class, &sHelpInfo_Ss0Status,\n", rel)
    out[rel] = text
    return out
