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
# The seals' animation on the map (C-SkillSys, MIT): the flash on the unit, and Heavy Gravity's falling sprite on the foe
SEAL_ANIM_URLS = {
    "skill_anim_fem": f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Data/SkillSys/SkillMapAnim/skill-mapanimap.png",
    "heavy_gravity_fem": (f"https://raw.githubusercontent.com/{REPO}/{COMMIT}"
                          "/Kernel/Wizardry/Common/MapAnims/HeavyGravity/Source/Img_HeavyGravity.png"),
}
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
    stats: tuple = ()     # (stat, value) pairs added by the stat getters: 0 Str, 1 Skl, 2 Spd, 3 Def, 4 Res, 5 Lck, 6 Mag
    when: str = ""        # stats: "low" (under 25 % of HP), "full" (HP full), "light" (3 items or less)
    code: str = ""        # battle skills: C run in ComputeBattleUnitStats once both units' stats are computed (attacker,
    # defender); late skills: at the start of ComputeBattleUnitEffectiveStats (comparisons with the foe, as C-SkillSys's
    # BattleCalcReal); proc skills: C run on a hit before its damage (attacker, defender, magic, *attack, *defense)
    after: str = ""       # proc skills: C run on the hit's damage, after the critical roll
    effect: str = ""      # proc skills: C run once the hit's HP change is done (hit, allowed, status, keep; _hit_skills)
    roll: str = ""        # proc skills: C run before the hit roll (attacker, defender, rate: the hit rate; _hit_skills)
    game: str = ""        # game skills: the C condition on `unit`
    menu: str = ""        # menu skills: the command's name in the unit menu
    holder: str = "attacker"   # battle, late and eff skills: whose skill it is (the code reads attacker and defender)
    group: str = ""       # FE Maker's category in the skill picker (skill.kind.<group>); the kind when empty
    magic: bool = False   # only with the Strength / Magic split
    side: str = ""        # aura skills: whose battles they act on, "ally", "foe" or "both" of the holder; "self": the
    # holder's own, by the units around it (allies1..3, foes1..3: within 1 to 3 tiles)
    reach: int = 0        # aura skills: the greatest distance (in tiles) from the holder

    @property
    def category(self) -> str:
        return self.group or self.kind


def _stat(sid, icon, stat, value, defiant, text):
    return Skill(sid, "stat", icon, text, ((stat, value),), "low" if defiant else "", group="hp" if defiant else "")


ALL_STATS = (0, 1, 2, 3, 4, 5, 6)


def _push(sid, stat, text):
    stats = tuple((k, 5) for k in (ALL_STATS if stat is None else (stat,)))
    return Skill(sid, "stat", sid, text, stats, "full", group="hp", magic=stat == 6)


def _b(sid, group, text, code, kind="battle", icon=None, **more):
    """A battle skill (C-SkillSys's PreBattleCalcAttackerSkills; `late`: its BattleCalcReal comparisons); icon "":
    none at the pinned commit, a "?" is drawn."""
    return Skill(sid, kind, sid if icon is None else icon, text, code=code, group=group, **more)


def _aura(sid, side, reach, text, code):
    """An aura (C-SkillSys's PreBattleCalcAuraEffect): `code` changes `attacker`, the unit in battle, when the holder
    `unit` is on `side` of it within `reach` tiles."""
    return Skill(sid, "aura", sid, text, code=code, group="aura", side=side, reach=reach)


_LOW = "(attacker->hpInitial * 4 < attacker->unit.maxHP)"
_HALF = "(attacker->unit.maxHP > attacker->unit.curHP * 2)"
_FIRST = "(attacker == &gBattleActor)"
_TARGET = "(attacker == &gBattleTarget)"
_MAGIC = "((%s)->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE))"
# batch 10, the seals: their name, help label, stat (gamedata.TEMP_STATS's counter)
SEALS = (("Strength", "Attack", "STR", 0), ("Magic", "Magic", "MAG", 6), ("Skill", "Skill", "SKL", 1),
         ("Speed", "Speed", "SPD", 2), ("Luck", "Luck", "LUCK", 5), ("Defense", "Defense", "DEF", 3),
         ("Resistance", "Resistance", "RES", 4))
_TOME = "({0}->weaponType == ITYPE_ANIMA || {0}->weaponType == ITYPE_LIGHT || {0}->weaponType == ITYPE_DARK)"

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
          code=f"if {_LOW} attacker->battleCritRate += 50;", group="hp"),
    Skill("DefiantAvoid", "battle", "DefiantAvoid", "Defiant Avoid:[NL]Avoid Rate +30%,[NL]if HP < 25%.",
          code=f"if {_LOW} attacker->battleAvoidRate += 30;", group="hp"),
    Skill("BlowDarting", "battle", "BlowDarting", "Darting Blow:[NL]If unit initiates combat,[NL]grants +6 AS during combat.",
          code=f"if {_FIRST} attacker->battleSpeed += 6;", group="initiative"),
    Skill("BlowDeath", "battle", "BlowDeath", "Death Blow:[NL]If unit initiates combat,[NL]grants +6 STR during combat.",
          code=f"if ({_FIRST} && !{_MAGIC % 'attacker'}) attacker->battleAttack += 6;", group="initiative"),
    Skill("BlowArmored", "battle", "BlowArmored", "Armored Blow:[NL]If unit initiates combat,[NL]grants +6 DEF during combat.",
          code=f"if ({_FIRST} && !{_MAGIC % 'defender'}) attacker->battleDefense += 6;", group="initiative"),
    Skill("BlowWarding", "battle", "BlowWarding", "Warding Blow:[NL]If unit initiates combat,[NL]grants +6 RES during combat.",
          code=f"if ({_FIRST} && {_MAGIC % 'defender'}) attacker->battleDefense += 6;", group="initiative"),
    Skill("Wrath", "battle", "Wrath", "Wrath:[NL]If current HP is < 50%[NL]of max, +20 Crit Rate.",
          code=f"if {_HALF} attacker->battleCritRate += 20;", group="hp"),
    Skill("Vantage", "order", "Vantage", "Vantage:[NL]When unit is defender while[NL]their HP is < 50%, attack first."),
    Skill("Desperation", "order", "Desperation",
          "Desperation:[NL]When unit attacks with HP < 50%,[NL]its follow-up comes at once."),
    # lot 7: the order of the rounds (C-SkillSys's BattleOrder.c, _battle_order)
    Skill("QuickRiposte", "order", "QuickRiposte",
          "Quick Riposte:[NL]If unit is attacked while their[NL]HP > 50%, they attack twice."),
    Skill("VengefulFighter", "order", "VengefulFighter",
          "Vengeful Fighter:[NL]If HP is higher than 50%,[NL]always attack twice when under attack."),
    Skill("BoldFighter", "order", "BoldFighter",
          "Bold Fighter:[NL]If HP is higher than 50%,[NL]always attack twice when attacking."),
    Skill("RecklessFighter", "order", "RecklessFighter",
          "Reckless Fighter:[NL]If HP is higher than 50%,[NL]both sides always attack twice."),
    Skill("WaryFighter", "order", "WaryFighter", "Wary Fighter:[NL]Prevents the foe's follow-up[NL]if unit's HP > 50%."),
    Skill("BidingBlow", "order", "", "Biding Blow:[NL]Attack twice if the enemy[NL]cannot counterattack."),
    Skill("BrashAssault", "order", "BrashAssault", "Brash Assault:[NL]If foe can counter,[NL]follow-up attack is guaranteed."),
    Skill("AdvantageChaser", "order", "AdvantageChaser",
          "Advantage Chaser:[NL]Unit always doubles if they have[NL]Weapon Triangle Advantage."),
    Skill("PassionsFlow", "order", "PassionsFlow", "Passions Flow:[NL]Unit doubles if currently[NL]gaining support bonuses."),
    Skill("PridefulWarrior", "order", "PridefulWarrior",
          "Prideful Warrior:[NL]Unit always attacks last in[NL]the round, but always doubles."),
    Skill("LastWord", "order", "", "Last Word:[NL]If the enemy doubles,[NL]this unit doubles."),
    Skill("GaleWings", "order", "GaleWings", "Gale Wings:[NL]When unit is defender while[NL]their HP is 100%, attack first."),
    Skill("YngviAscendant", "order", "YngviAscendant",
          "Yngvi Ascendant:[NL]Follow-up attack cannot be nullified[NL]and occurs immediately if exists."),
    Skill("Dazzle", "order", "Dazzle", "Dazzle:[NL]Enemy cannot counterattack[NL]this unit."),
    Skill("Moonlight", "order", "Moonlight", "Moonlight:[NL]This unit cannot double, but[NL]the enemy cannot counterattack."),
    Skill("Pursuer", "battle", "Pursuer",
          "Pursuer: If initiating combat,[NL]attack speed +5, attack + 25% of unit[NL]speed, double attack immediately.",
          code="if (attacker == &gBattleActor) {\n            attacker->battleSpeed += 5;\n"
               "            attacker->battleAttack += attacker->unit.spd / 4;\n        }", group="order"),
    Skill("CloseCombat", "battle", "CloseCombat",
          "Close Combat: +2 damage if at[NL]1 range. Your double attacks[NL]occur before countering.",
          code="if (gBattleStats.range == 1) attacker->battleAttack += 2;", group="order"),
    Skill("DoubleLion", "hits", "DoubleLion",
          "Double Lion:[NL]If unit attacks with full HP,[NL]bestow Brave effect and lose 1 HP.",
          code="if (unit == &gBattleActor && SkillTesterFem(&unit->unit, SKILL_FEM_DoubleLion)\n"
               "            && unit->hpInitial == unit->unit.maxHP)\n            more += 1;"),
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
    # batch 10, triggered skills (C-SkillSys's BattleHit.c, BattleHitAttr.c, SkillActRate.c); its Great Shield and Sure
    # Shot are the game's (GAME_SKILLS, Level %)
    Skill("Counter", "proc", "Counter", "Counter:[NL]Reflect physical damage[NL]dealt at melee range."),
    Skill("CounterMagic", "proc", "CounterMagic", "Counter Magic:[NL]Reflect magical damage[NL]dealt at range."),
    Skill("DevilsPact", "proc", "DevilsPact", "Devil's Pact:[NL]Inflict the Devil effect[NL]upon the enemy unit."),
    Skill("DevilsWhim", "proc", "DevilsWhim", "Devil's Whim:[NL]Inflict the Devil effect[NL]upon both units."),
    Skill("DevilsLuck", "proc", "DevilsLuck", "Devil's Luck:[NL]Give the unit's devil effect[NL]to the enemy in battle."),
    Skill("AxeFaith", "proc", "AxeFaith", "Axefaith:[NL]When attacking with an Axe,[NL]hit + attack. (Attack % activation).",
          roll="if (attacker->weaponType == ITYPE_AXE\n"
               "            && SkillProcRateFem(attacker, SKILL_FEM_AxeFaith, attacker->battleAttack))\n"
               "            rate += attacker->battleAttack;"),
    Skill("Pass", "map", "Pass", "Pass:[NL]Unit can pass through[NL]enemies if HP >= 25%.", group="map"),
    Skill("Bargain", "map", "Bargain", "Bargain:[NL]Reduce cost of items bought[NL]by this unit by 50%.", group="items"),
    Skill("Deal", "map", "", "Deal:[NL]Reduce cost of items bought[NL]by this unit by 20%.", group="items"),
    Skill("RightfulKing", "proc", "RightfulKing",
          "Rightful King:[NL]Add +10% to the activation[NL]rate of this unit's skills."),
    Skill("RightfulGod", "proc", "RightfulGod",
          "Rightful God:[NL]Add +30% to the activation[NL]rate of this unit's skills."),
    Skill("Hero", "proc", "Hero", "Hero:[NL]If unit's HP < 50%, add +30%[NL]to its skills' activation rate."),
    Skill("Adept", "hits", "Adept", "Adept:[NL]Attacks one more time[NL]when HP is full.",
          code="if (SkillTesterFem(&unit->unit, SKILL_FEM_Adept) && unit->hpInitial == unit->unit.maxHP)\n"
               "            more += 1;"),
    Skill("Astra", "hits", "Astra", "Astra:[NL]Unit attacks 5 times but damage[NL]is halved. (SPD % activation).",
          code="if (unit == &gBattleActor && SkillProcRateFem(unit, SKILL_FEM_Astra, unit->unit.spd)) {\n"
               "            sAstraFem = TRUE;\n            more += 4;\n        }",
          after="if (sAstraFem && attacker == &gBattleActor) {\n            gBattleStats.damage /= 2;\n"
                "            /* its name on each of its hits, as C-SkillSys's round skills */\n"
                "            if (gBattleHitIterator < gBattleHitArray + BATTLE_HIT_MAX)\n"
                "                sSkillShownFem[(gBattleHitIterator - gBattleHitArray) * 2] = SKILL_FEM_Astra;\n"
                "        }"),
    Skill("Aegis", "proc", "Aegis", "Aegis:[NL]Nullifies a magic attack.[NL](Skill % activation).",
          code="if (magic && SkillProcFem(defender, SKILL_FEM_Aegis))\n"
               "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_GREATSHLD;"),
    # batch 4, on the map (_map_skills): C-SkillSys's PostActionSkills/Canto.c, PrePhaseSkills/PrePhaseHeal.c, Tsuzuku.c
    Skill("CantoPlus", "map", "CantoPlus", "Canto+:[NL]Unit can move again after[NL]any action, combat included."),
    Skill("Renewal", "map", "Renewal", "Renewal:[NL]Restores 30% of max HP[NL]at the start of each turn."),
    # batch 9, heals at the start of the phase (PrePhaseHeal.c, HEAL_SKILLS)
    Skill("Imbue", "map", "Imbue", "Imbue:[NL]Recover HP equal to MAG[NL]at the start of each turn.", magic=True),
    Skill("Forager", "map", "Forager", "Forager:[NL]Recover 20% HP each turn if[NL]on a Plain, Forest or Mountain."),
    Skill("RainDish", "map", "RainDish", "RainDish:[NL]If it is raining, restore 30%[NL]of max HP at the start of each turn."),
    Skill("Relief", "map", "Relief",
          "Relief:[NL]Restore 20% of max HP at the start[NL]of turn, if no allies within 2 tiles."),
    Skill("Camaraderie", "map", "Camaraderie",
          "Camaraderie:[NL]Restore 10% of max HP at the start[NL]of turn, if allies within 2 tiles."),
    Skill("Amaterasu", "map", "Amaterasu", "Amaterasu:[NL]Allies within 2 tiles[NL]recover 20% HP each turn."),
    # batch 9, the enemy AI's targets (_ai_skills)
    Skill("Shade", "ai", "Shade", "Shade: Enemies are less[NL]likely to target this unit."),
    Skill("ShadePlus", "ai", "ShadePlus", "Shade+: Enemies won't[NL]target this unit."),
    Skill("Provoke", "ai", "Provoke", "Provoke: Enemies are more[NL]likely to target this unit."),
    # batch 4, unit menu commands (_menu_skills): C-SkillSys's MenuSkills/HerosMovement
    Skill("Pivot", "menu", "Pivot", "Pivot:[NL]Unit can move to the other[NL]side of an adjacent ally.", menu="Pivot"),
    Skill("Reposition", "menu", "Reposition", "Reposition:[NL]Moves an adjacent ally to[NL]the other side of the unit.",
          menu="Reposition"),
    Skill("Shove", "menu", "Shove", "Shove:[NL]Pushes an adjacent ally[NL]one tile away.", menu="Shove"),
    Skill("Swap", "menu", "Swap", "Swap:[NL]Unit switches places with[NL]an adjacent ally.", menu="Swap"),
    # batch 10: C-SkillSys's Smite.c and Rally.c
    Skill("Smite", "menu", "Smite", "Smite:[NL]Pushes an adjacent ally[NL]two tiles away.", menu="Smite"),
    *(Skill(f"Rally{name}", "menu", f"Rally{name}", f"Rally {label}:[NL]+4 {short} to all allies[NL]within 2 tiles of the unit.",
            menu=f"Rally-{word}", magic=stats == (6,)) for name, label, short, word, stats in (
        ("Strength", "Strength", "STR", "Str", (0,)), ("Magic", "Magic", "MAG", "Mag", (6,)),
        ("Skill", "Skill", "SKL", "Skl", (1,)),
        ("Speed", "Speed", "SPD", "Spd", (2,)), ("Luck", "Luck", "LCK", "Lck", (5,)),
        ("Defense", "Defense", "DEF", "Def", (3,)), ("Resistance", "Resistance", "RES", "Res", (4,)),
        ("Spectrum", "Spectrum", "all stats", "Spec", (0, 1, 2, 3, 4, 5, 6)))),
    Skill("Galeforce", "map", "Galeforce",
          "Galeforce:[NL]Acts again after defeating[NL]an enemy, once a turn."),
    # batch 10, after the battle (_post_action_skills: C-SkillSys's PostActionSkills, with the map's damage and heal
    # animations; values from SkillExtraInfo.c)
    Skill("Fury", "stat", "Fury", "Fury:[NL]All stats +3,[NL]HP -6 after combat.", tuple((k, 3) for k in ALL_STATS),
          group="after"),
    Skill("GrislyWound", "map", "GrislyWound", "Grisly Wound:[NL]After combat, the foe[NL]loses 20% of its max HP.",
          group="after"),
    Skill("PoisonStrike", "map", "PoisonStrike", "Poison Strike:[NL]After attacking, the foe[NL]loses 20% of its max HP.",
          group="after"),
    Skill("Lifetaker", "map", "Lifetaker", "Lifetaker:[NL]Restores 25% of max HP[NL]after defeating an enemy.",
          group="after"),
    Skill("Despoil", "map", "Despoil", "Despoil:[NL]Gain a Red Gem after[NL]defeating an enemy (SKL %).",
          group="after"),
    Skill("SavageBlow", "map", "SavageBlow", "Savage Blow:[NL]After attacking, enemies[NL]within 2 tiles take 20% damage.",
          group="after"),
    Skill("Lunge", "map", "Lunge", "Lunge:[NL]Swap positions with the enemy[NL]after attacking them.", group="after"),
    Skill("BreathOfLife", "map", "BreathOfLife", "Breath of Life:[NL]After attacking, allies[NL]in 2 tiles heal 20% HP.",
          group="after"),
    # the seals (C-SkillSys's PostActionSkills/SealSkills.c): -6 on the foe's stat, back by 1 each turn, on the items'
    # temporary bonuses (gamedata.TEMP_BONUS_MACROS)
    *(Skill(f"Seal{name}", "map", f"Seal{name}", f"Seal {label}:[NL]After hitting, foe's {short}[NL]-6, back 1 per turn.",
            group="after", magic=stat == 6)
      for name, label, short, stat in SEALS),
    # batch 10, growths and experience (_growth_skills: C-SkillSys's GrowthGetter.c, BattleExp.c and BattleHit.c)
    Skill("Blossom", "map", "Blossom", "Blossom:[NL]2x growth rates,[NL]but 1/2 EXP gain.", group="growth"),
    Skill("Aptitude", "map", "Aptitude", "Aptitude:[NL]+20% to all[NL]growth rates.", group="growth"),
    Skill("Paragon", "map", "Paragon", "Paragon:[NL]Experience gained[NL]is doubled.", group="growth"),
    Skill("Discipline", "map", "Discipline", "Discipline:[NL]Weapon experience gains[NL]are doubled.",
          group="growth"),
    # batch 5, simple passives (C-SkillSys's getters, PreBattleCalcAttackerSkills and BattleCalcReal; values from
    # SkillExtraInfo.c)
    _push("PushStrength", 0, "Push Strength:[NL]+5 STR if HP is full."),
    _push("PushMagic", 6, "Push Magic:[NL]+5 MAG if HP is full."),
    _push("PushSkill", 1, "Push Skill:[NL]+5 SKL if HP is full."),
    _push("PushSpeed", 2, "Push Speed:[NL]+5 SPD if HP is full."),
    _push("PushLuck", 5, "Push Luck:[NL]+5 LUCK if HP is full."),
    _push("PushDefense", 3, "Push Defense:[NL]+5 DEF if HP is full."),
    _push("PushResistance", 4, "Push Resistance:[NL]+5 RES if HP is full."),
    _push("PushSpectrum", None, "Push Spectrum:[NL]+5 to all stats[NL]if HP is full."),
    Skill("FortressDef", "stat", "FortressDef", "Fortress Def:[NL]STR/MAG -3, DEF +5.", ((0, -3), (6, -3), (3, 5))),
    Skill("FortressRes", "stat", "FortressRes", "Fortress Res:[NL]STR/MAG -3, RES +5.", ((0, -3), (6, -3), (4, 5))),
    # batch 10 (Mangs' list, docs/rapport-competences.md), from C-SkillSys's status getters
    Skill("LifeAndDeath", "stat", "LifeAndDeath", "Life and Death:[NL]STR/MAG/SKL/SPD +5,[NL]DEF/RES -5.",
          ((0, 5), (6, 5), (1, 5), (2, 5), (3, -5), (4, -5))),
    Skill("LightWeight", "stat", "LightWeight", "Light Weight:[NL]SPD +3 if unit has[NL]3 items or less.", ((2, 3),),
          "light"),
    # when the unit attacks
    _b("BlowFiendish", "initiative", "Fiendish Blow:[NL]If unit initiates combat,[NL]grants +6 MAG during combat.",
       f"if ({_FIRST} && {_MAGIC % 'attacker'}) attacker->battleAttack += 6;"),
    _b("BlowDuelist", "initiative", "Duelist's Blow:[NL]If unit initiates combat,[NL]grants +20 Avoid.",
       f"if {_FIRST} attacker->battleAvoidRate += 20;"),
    _b("BlowUncanny", "initiative", "Uncanny Blow:[NL]If unit initiates combat,[NL]grants +30 Hit.",
       f"if {_FIRST} attacker->battleHitRate += 30;"),
    _b("BlowKilling", "initiative", "Killing Blow:[NL]If unit initiates combat,[NL]grants +20 Crit.",
       f"if {_FIRST} attacker->battleCritRate += 20;"),
    _b("ArcaneBlade", "initiative", "Arcane Blade:[NL]Initiating at 1 range:[NL]Hit and Crit +3+(MAG/2).",
       f"if ({_FIRST} && gBattleStats.range == 1) {{\n"
       "            attacker->battleCritRate += GetUnitMagicFem(&attacker->unit) / 2 + 3;\n"
       "            attacker->battleHitRate += GetUnitMagicFem(&attacker->unit) / 2 + 3;\n        }", magic=True),
    _b("Prescience", "initiative", "Prescience:[NL]Initiating at 1 range:[NL]Hit and Avoid +15.",
       f"if ({_FIRST} && gBattleStats.range == 1) {{\n"
       "            attacker->battleHitRate += 15;\n            attacker->battleAvoidRate += 15;\n        }"),
    _b("QuickDraw", "initiative", "Quick Draw:[NL]If unit initiates combat,[NL]attack +4.",
       f"if {_FIRST} attacker->battleAttack += 4;"),
    _b("Charge", "initiative", "Charge:[NL]+1 damage for every[NL]two tiles moved.",
       f"if {_FIRST} attacker->battleAttack += gActionData.moveCount / 2;"),
    _b("Outrider", "initiative", "Outrider:[NL]+1 DEF and +3% crit[NL]per tile moved.",
       f"if {_FIRST} {{\n            attacker->battleDefense += gActionData.moveCount;\n"
       "            attacker->battleCritRate += gActionData.moveCount * 3;\n        }"),
    # when the unit is attacked
    _b("StanceBracing", "attacked", "Bracing Stance:[NL]Grants +4 DEF and RES[NL]if attacked.",
       f"if {_TARGET} attacker->battleDefense += 4;"),
    _b("StanceDarting", "attacked", "Darting Stance:[NL]Grants +6 AS if attacked.", f"if {_TARGET} attacker->battleSpeed += 6;"),
    _b("StanceFierce", "attacked", "Fierce Stance:[NL]Grants +6 ATK if attacked.", f"if {_TARGET} attacker->battleAttack += 6;"),
    _b("StanceKestrel", "attacked", "Kestrel Stance:[NL]Grants +4 ATK and AS[NL]if attacked.",
       f"if {_TARGET} {{\n            attacker->battleAttack += 4;\n            attacker->battleSpeed += 4;\n        }}"),
    _b("StanceMirror", "attacked", "Mirror Stance:[NL]Grants +4 ATK and RES[NL]if attacked.",
       f"if {_TARGET} {{\n            attacker->battleAttack += 4;\n"
       f"            if {_MAGIC % 'defender'}\n                attacker->battleDefense += 4;\n        }}"),
    _b("StanceReady", "attacked", "Ready Stance:[NL]Grants +4 AS and DEF[NL]if attacked.",
       f"if {_TARGET} {{\n            attacker->battleSpeed += 4;\n"
       f"            if (!{_MAGIC % 'defender'})\n                attacker->battleDefense += 4;\n        }}"),
    _b("StanceSteady", "attacked", "Steady Stance:[NL]Grants +6 DEF if attacked.",
       f"if ({_TARGET} && !{_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    _b("StanceSturdy", "attacked", "Sturdy Stance:[NL]Grants +4 ATK and DEF[NL]if attacked.",
       f"if {_TARGET} {{\n            attacker->battleAttack += 4;\n"
       f"            if (!{_MAGIC % 'defender'})\n                attacker->battleDefense += 4;\n        }}"),
    _b("StanceSwift", "attacked", "Swift Stance:[NL]Grants +4 AS and RES[NL]if attacked.",
       f"if {_TARGET} {{\n            attacker->battleSpeed += 4;\n"
       f"            if {_MAGIC % 'defender'}\n                attacker->battleDefense += 4;\n        }}"),
    _b("StanceWarding", "attacked", "Warding Stance:[NL]Grants +6 RES if attacked.",
       f"if ({_TARGET} && {_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    _b("StanceSpectrum", "attacked", "Spectrum Stance:[NL]Grants +2 ATK, AS, DEF[NL]and RES if attacked.",
       f"if {_TARGET} {{\n            attacker->battleAttack += 2;\n            attacker->battleSpeed += 2;\n"
       "            attacker->battleDefense += 2;\n        }"),
    _b("Patience", "attacked", "Patience:[NL]When under attack,[NL]avoid +10.", f"if {_TARGET} attacker->battleAvoidRate += 10;"),
    _b("Pursuit", "attacked", "Pursuit:[NL]When under attack,[NL]attack speed +2.", f"if {_TARGET} attacker->battleSpeed += 2;"),
    _b("StrongRiposte", "attacked", "Strong Riposte:[NL]When under attack,[NL]damage +3.",
       f"if {_TARGET} attacker->battleAttack += 3;"),
    # by weapon type
    *(_b(f"Crit{w}", "weapon", f"Crit {name}:[NL]Crit rate +10%, if[NL]{art} {name} is equipped.",
         f"if (attacker->weaponType == ITYPE_{t}) attacker->battleCritRate += 10;")
      for w, name, art, t in (("Sword", "Sword", "a", "SWORD"), ("Lance", "Lance", "a", "LANCE"), ("Axe", "Axe", "an", "AXE"),
                              ("Bow", "Bow", "a", "BOW"))),
    *(_b(f"Faire{w}", "weapon", f"{name} Faire:[NL]Atk +5 if unit[NL]equips {art} {name}.",
         f"if ({cond}) attacker->battleAttack += 5;")
      for w, name, art, cond in (
          ("Sword", "Sword", "a", "attacker->weaponType == ITYPE_SWORD"),
          ("Lance", "Lance", "a", "attacker->weaponType == ITYPE_LANCE"),
          ("Axe", "Axe", "an", "attacker->weaponType == ITYPE_AXE"),
          ("Bow", "Bow", "a", "attacker->weaponType == ITYPE_BOW"),
          ("BMag", "Tome", "a", "attacker->weaponType == ITYPE_ANIMA || attacker->weaponType == ITYPE_LIGHT"
                                " || attacker->weaponType == ITYPE_DARK"),
          ("Anima", "Anima", "an", "attacker->weaponType == ITYPE_ANIMA"),
          ("Light", "Light", "a", "attacker->weaponType == ITYPE_LIGHT"),
          ("Dark", "Dark", "a", "attacker->weaponType == ITYPE_DARK"))),
    _b("AvoidSword", "weapon", "Avoid Sword:[NL]Avoid +20% if[NL]a Sword is equipped.",
       "if (attacker->weaponType == ITYPE_SWORD) attacker->battleAvoidRate += 20;"),
    _b("HolyAura", "weapon", "Holy Aura:[NL]Dmg +1, Hit, Avoid and[NL]Crit +5% with Light.",
       "if (attacker->weaponType == ITYPE_LIGHT) {\n            attacker->battleAttack += 1;\n"
       "            attacker->battleCritRate += 5;\n            attacker->battleHitRate += 5;\n"
       "            attacker->battleAvoidRate += 5;\n        }"),
    _b("LadyBlade", "weapon", "Lady Blade:[NL]If this unit is female,[NL]double weapon might.",
       "if (UNIT_CATTRIBUTES(&attacker->unit) & CA_FEMALE) attacker->battleAttack += GetItemMight(attacker->weapon);"),
    # by HP
    _b("Perfectionist", "hp", "Perfectionist:[NL]+15 Hit and Avoid when[NL]HP is at maximum.",
       "if (attacker->hpInitial == attacker->unit.maxHP) {\n            attacker->battleHitRate += 15;\n"
       "            attacker->battleAvoidRate += 15;\n        }"),
    _b("WindDisciple", "hp", "Wind Disciple:[NL]+10 Hit and Avoid when[NL]HP is not at max.",
       "if (attacker->hpInitial < attacker->unit.maxHP) {\n            attacker->battleHitRate += 10;\n"
       "            attacker->battleAvoidRate += 10;\n        }"),
    _b("FieryBlood", "hp", "Fiery Blood:[NL]+4 attack if HP[NL]is not at max.",
       "if (attacker->hpInitial < attacker->unit.maxHP) attacker->battleAttack += 4;"),
    _b("FireBoost", "hp", "Fire Boost:[NL]ATK +6 if HP is at least[NL]3 higher than the foe's.",
       "if (attacker->hpInitial >= defender->hpInitial + 3) attacker->battleAttack += 6;"),
    _b("WindBoost", "hp", "Wind Boost:[NL]SPD +6 if HP is at least[NL]3 higher than the foe's.",
       "if (attacker->hpInitial >= defender->hpInitial + 3) attacker->battleSpeed += 6;"),
    _b("EarthBoost", "hp", "Earth Boost:[NL]DEF +6 if HP is at least[NL]3 higher than the foe's.",
       f"if (attacker->hpInitial >= defender->hpInitial + 3 && !{_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    _b("WaterBoost", "hp", "Water Boost:[NL]RES +6 if HP is at least[NL]3 higher than the foe's.",
       f"if (attacker->hpInitial >= defender->hpInitial + 3 && {_MAGIC % 'defender'}) attacker->battleDefense += 6;"),
    # by the foe
    _b("Chivalry", "foe", "Chivalry:[NL]When foe is at full HP,[NL]attack and DEF/RES +2.",
       "if (defender->hpInitial == defender->unit.maxHP) {\n            attacker->battleAttack += 2;\n"
       "            attacker->battleDefense += 2;\n        }"),
    _b("Pragmatic", "foe", "Pragmatic:[NL]When foe is not at full HP,[NL]attack +3 and DEF/RES +1.",
       "if (defender->hpInitial < defender->unit.maxHP) {\n            attacker->battleAttack += 3;\n"
       "            attacker->battleDefense += 1;\n        }"),
    _b("StoneBody", "foe", "Stone Body:[NL]If CON is greater than[NL]the foe's, damage + the gap.",
       "if (UNIT_CON(&attacker->unit) > UNIT_CON(&defender->unit))\n"
       "            attacker->battleAttack += UNIT_CON(&attacker->unit) - UNIT_CON(&defender->unit);"),
    _b("Trample", "foe", "Trample:[NL]+5 damage to[NL]unmounted units.",
       "if (!(UNIT_CATTRIBUTES(&defender->unit) & CA_MOUNTEDAID)) attacker->battleAttack += 5;"),
    _b("Opportunist", "foe", "Opportunist:[NL]+4 damage if the foe[NL]cannot counter.",
       "if (!defender->canCounter) attacker->battleAttack += 4;"),
    _b("Analytic", "foe", "Analytic:[NL]+10 ATK if SPD is 4 below[NL]the foe's; +5 if 1 to 3.",
       "if (defender->battleSpeed - attacker->battleSpeed >= 4)\n            attacker->battleAttack += 10;\n"
       "        else if (defender->battleSpeed > attacker->battleSpeed)\n            attacker->battleAttack += 5;"),
    _b("MageSlayer", "foe", "Mage Slayer:[NL]+2 damage and +10% crit[NL]against magic users.",
       "if (defender->unit.ranks[ITYPE_ANIMA] || defender->unit.ranks[ITYPE_LIGHT] || defender->unit.ranks[ITYPE_DARK]"
       " || defender->unit.ranks[ITYPE_STAFF]) {\n            attacker->battleAttack += 2;\n"
       "            attacker->battleCritRate += 10;\n        }"),
    # batch 10: the breakers, from C-SkillSys's weapon triangle confs (Data/BattleSys/Source/WeaponTriangle.c): only
    # with the weapon that beats the foe's (C-SkillSys's choice; the official games' breakers work with any weapon)
    *(_b(sid, "foe", f"{name}:[NL]Hit and Avoid +20 using[NL]{mine} against {theirs}.",
         f"if ({own} && {foe}) {{\n            attacker->battleHitRate += 20;\n"
         "            attacker->battleAvoidRate += 20;\n        }", icon="" if sid == "BMagBreaker" else None)
      for sid, name, mine, theirs, own, foe in (
          ("SwordBreaker", "Swordbreaker", "a Lance", "a Sword", "attacker->weaponType == ITYPE_LANCE",
           "defender->weaponType == ITYPE_SWORD"),
          ("LanceBreaker", "Lancebreaker", "an Axe", "a Lance", "attacker->weaponType == ITYPE_AXE",
           "defender->weaponType == ITYPE_LANCE"),
          ("AxeBreaker", "Axebreaker", "a Sword", "an Axe", "attacker->weaponType == ITYPE_SWORD",
           "defender->weaponType == ITYPE_AXE"),
          ("BowBreaker", "Bowbreaker", "a tome", "a Bow", _TOME.format("attacker"), "defender->weaponType == ITYPE_BOW"),
          ("BMagBreaker", "Tomebreaker", "a Bow", "a tome", "attacker->weaponType == ITYPE_BOW", _TOME.format("defender")))),
    _b("HeavyBlade", "foe", "Heavy Blade:[NL]If attack is higher than[NL]the foe's, crit +15%.",
       "if (attacker->battleAttack > defender->battleAttack) attacker->battleCritRate += 15;", kind="late"),
    Skill("HeavyBladePlus", "late", "HeavyBladePlus",
          "Heavy Blade+:[NL]STR +5. If attack is higher[NL]than the foe's, crit +25%.", ((0, 5),),
          code="if (attacker->battleAttack > defender->battleAttack) attacker->battleCritRate += 25;",
          group="foe"),
    _b("FlashingBlade", "foe", "Flashing Blade:[NL]If AS is higher than[NL]the foe's, crit +15%.",
       "if (attacker->battleSpeed > defender->battleSpeed) attacker->battleCritRate += 15;", kind="late"),
    # by the situation: range, terrain, turn, status
    _b("NaturalCover", "situation", "Natural Cover:[NL]-3 damage taken on[NL]terrain with effects.",
       "if (attacker->terrainDefense > 0 || attacker->terrainAvoid > 0 || attacker->terrainResistance > 0)\n"
       "            attacker->battleDefense += 3;"),
    _b("TowerShield", "situation", "Tower Shield:[NL]Gain 6 Defense against[NL]attacks at range.",
       "if (gBattleStats.range >= 2) attacker->battleDefense += 6;"),
    _b("ShortShield", "situation", "Short Shield:[NL]Gain 6 Defense against[NL]attacks in melee.",
       "if (gBattleStats.range == 1) attacker->battleDefense += 6;"),
    _b("Vanity", "situation", "Vanity:[NL]+2 damage and +10 Hit[NL]when fighting at 2 range.",
       "if (gBattleStats.range == 2) {\n            attacker->battleAttack += 2;\n"
       "            attacker->battleHitRate += 10;\n        }"),
    _b("EvenRhythm", "situation", "Even Rhythm:[NL]+10 Hit and Avoid on[NL]even numbered turns.",
       "if (gPlaySt.chapterTurnNumber % 2 == 0) {\n            attacker->battleHitRate += 10;\n"
       "            attacker->battleAvoidRate += 10;\n        }"),
    _b("OddRhythm", "situation", "Odd Rhythm:[NL]+10 Hit and Avoid on[NL]odd numbered turns.",
       "if (gPlaySt.chapterTurnNumber % 2 == 1) {\n            attacker->battleHitRate += 10;\n"
       "            attacker->battleAvoidRate += 10;\n        }"),
    _b("QuickBurn", "situation", "Quick Burn:[NL]+15 Hit and Avoid. This[NL]bonus decreases each turn.",
       "if (gPlaySt.chapterTurnNumber < 15) {\n            attacker->battleHitRate += 15 - gPlaySt.chapterTurnNumber;\n"
       "            attacker->battleAvoidRate += 15 - gPlaySt.chapterTurnNumber;\n        }"),
    _b("SlowBurn", "situation", "Slow Burn:[NL]+1 Hit and Avoid for each[NL]passing turn, up to 15.",
       "{\n            int turn = gPlaySt.chapterTurnNumber > 15 ? 15 : gPlaySt.chapterTurnNumber;\n\n"
       "            attacker->battleHitRate += turn;\n            attacker->battleAvoidRate += turn;\n        }"),
    _b("Guts", "situation", "Guts:[NL]+5 Attack if afflicted[NL]by any status condition.",
       "if (attacker->unit.statusIndex != UNIT_STATUS_NONE) attacker->battleAttack += 5;"),
    _b("StrongCon", "situation", "Strong Con:[NL]+5 Def/Res if afflicted[NL]by any status condition.",
       "if (attacker->unit.statusIndex != UNIT_STATUS_NONE) attacker->battleDefense += 5;"),
    _b("ElbowRoom", "situation", "Elbow Room:[NL]+3 damage dealt[NL]on open terrain.",
       "if (attacker->terrainDefense == 0 && attacker->terrainAvoid == 0 && attacker->terrainResistance == 0)\n"
       "            attacker->battleAttack += 3;"),
    _b("OutdoorFighter", "situation", "Outdoor Fighter:[NL]+10 Hit and Avoid when[NL]fighting outdoors.",
       "if (OutdoorTerrainFem(attacker->terrainId)) {\n            attacker->battleHitRate += 10;\n"
       "            attacker->battleAvoidRate += 10;\n        }"),
    # C-SkillSys's levels of the unit's earlier classes (GetUnitHiddenLevel) are not kept: 20 for a promoted unit
    _b("BattleVeteran", "battle", "Battle Veteran:[NL]+1 damage and +5 Hit[NL]per 10 levels.",
       "{\n            int tens = (attacker->unit.level"
       " + (UNIT_CATTRIBUTES(&attacker->unit) & CA_PROMOTED ? 20 : 0)) / 10;\n\n"
       "            attacker->battleAttack += tens;\n            attacker->battleHitRate += 5 * tens;\n        }"),
    _b("CriticalForce", "hit", "Critical Force:[NL]Base critical is[NL]SKL * 1.5, not SKL / 2.",
       "attacker->battleCritRate += attacker->unit.skl * 3 / 2 - attacker->unit.skl / 2;"),
    # always
    _b("Avoid", "battle", "Avoid +10:[NL]Avoid rate +10%.", "attacker->battleAvoidRate += 10;"),
    _b("Vigilance", "battle", "Vigilance:[NL]Gain +20 Avoid.", "attacker->battleAvoidRate += 20;"),
    # batch 6: hit and crit (BattleCalcReal_ComputSkills, after the game's effective rates), damage on each hit
    # (SkillEffects/BattleDamage), applied to the game's own damage after the critical roll
    Skill("Nullify", "map", "Nullify", "Nullify: Unit is protected[NL]from all effective attacks.", group="guard"),
    _b("KillingMachine", "hit", "Killing Machine:[NL]Double this unit's[NL]total crit rate.",
       "attacker->battleCritRate *= 2;", kind="late"),
    _b("Hawkeye", "hit", "Hawkeye:[NL]User will always hit[NL]the enemy.", "attacker->battleEffectiveHitRate = 100;",
       kind="eff"),
    _b("Merciless", "hit", "Merciless:[NL]Guaranteed critical hit[NL]against poisoned foes.",
       "if (defender->unit.statusIndex == UNIT_STATUS_POISON) attacker->battleEffectiveCritRate = 100;", kind="eff"),
    _b("Fortune", "hit", "Fortune:[NL]This unit cannot be crit.",
       "{\n            attacker->battleCritRate = 0;\n            attacker->battleEffectiveCritRate = 0;\n        }",
       kind="eff", holder="defender"),
    _b("Foresight", "hit", "Foresight:[NL]Foes cannot land[NL]critical hits on this unit.",
       "{\n            attacker->battleCritRate = 0;\n            attacker->battleEffectiveCritRate = 0;\n        }",
       kind="eff", holder="defender"),
    _b("SorceryBlade", "hit", "Sorcery Blade:[NL]Foe's defense is the lower[NL]of its DEF and RES.",
       "{\n            int phys = defender->terrainDefense + defender->unit.def;\n"
       "            int mag = defender->terrainResistance + defender->unit.res;\n"
       f"            int used = {_MAGIC % 'attacker'} ? mag : phys;\n\n"
       "            defender->battleDefense -= used - (phys < mag ? phys : mag);\n        }"),
    Skill("InfinityEdge", "proc", "InfinityEdge", "Infinity Edge:[NL]Critical attacks[NL]damage +100%.", group="damage",
          after="if ((gBattleHitIterator->attributes & BATTLE_HIT_ATTR_CRIT)"
                " && SkillTesterFem(&attacker->unit, SKILL_FEM_InfinityEdge))\n"
                "            gBattleStats.damage = gBattleStats.damage * 4 / 3;"),
    Skill("LunaAttack", "proc", "LunaAttack", "Luna Attack:[NL]Deals extra damage equal[NL]to a quarter of foe's DEF.",
          group="damage", after="if (SkillTesterFem(&attacker->unit, SKILL_FEM_LunaAttack))\n"
                                "            gBattleStats.damage += defender->battleDefense / 4;"),
    Skill("Flare", "proc", "Flare", "Flare:[NL]Halves enemy defenses.[NL](Skill % activation).", group="damage",
          code="if (SkillProcFem(attacker, SKILL_FEM_Flare))\n            *defense /= 2;"),
    Skill("Glacies", "proc", "Glacies", "Glacies:[NL]Adds unit's RES to damage.[NL](Skill % activation).", group="damage",
          code="if (SkillProcFem(attacker, SKILL_FEM_Glacies))\n            *attack += attacker->unit.res;"),
    Skill("Vengeance", "proc", "Vengeance", "Vengeance:[NL]Adds damage taken to attack.[NL](Skill % activation).",
          group="damage", code="if (SkillProcFem(attacker, SKILL_FEM_Vengeance))\n"
                              "            *attack += attacker->unit.maxHP - attacker->unit.curHP;"),
    Skill("DragonFang", "proc", "DragonFang", "Dragon Fang:[NL]Damage +50%.[NL](Skill x 2 % activation).", group="damage",
          after="if (SkillProcRateFem(attacker, SKILL_FEM_DragonFang, attacker->unit.skl * 2))\n"
                "            gBattleStats.damage += gBattleStats.damage / 2;"),
    Skill("Impale", "proc", "Impale", "Impale:[NL]Damage +300%.[NL](Skill % activation).", group="damage",
          after="if (!(gBattleHitIterator->attributes & (BATTLE_HIT_ATTR_CRIT | BATTLE_HIT_ATTR_SILENCER))"
                " && SkillProcFem(attacker, SKILL_FEM_Impale)) {\n"
                "            gBattleStats.damage *= 4;\n"
                "            gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_CRIT;\n        }"),
    Skill("Bane", "proc", "Bane", "Bane:[NL]Leaves the foe at 1 HP.[NL](Skill % activation).", group="damage",
          after="if (defender->unit.curHP > 1 && SkillProcFem(attacker, SKILL_FEM_Bane))\n"
                "            gBattleStats.damage = defender->unit.curHP - 1;"),
    Skill("Mercy", "proc", "Mercy", "Mercy:[NL]Leaves the foe at 1 HP if[NL]the attack would kill.[NL](Skill %)",
          group="damage", after="if (gBattleStats.damage >= defender->unit.curHP && defender->unit.curHP > 1"
                                " && SkillProcFem(attacker, SKILL_FEM_Mercy))\n"
                                "            gBattleStats.damage = defender->unit.curHP - 1;"),
    Skill("Eclipse", "proc", "Eclipse", "Eclipse:[NL]Halves the foe's current HP.[NL](Skill % activation).",
          group="damage", after="if (defender->unit.curHP > 1 && SkillProcFem(attacker, SKILL_FEM_Eclipse))\n"
                                "            gBattleStats.damage = (defender->unit.curHP + 1) >> 1;"),   # the Eclipse tome
    # lot 8: survive a deadly hit (C-SkillSys's CheckBattleInori, after Mercy)
    Skill("Inori", "proc", "Inori", "Inori:[NL]Unit may not die if attacked[NL]to 0 HP (Luck % activation).", group="guard",
          after="if (gBattleStats.damage >= defender->unit.curHP\n"
                "            && SkillProcRateFem(defender, SKILL_FEM_Inori, defender->unit.lck))\n"
                "            gBattleStats.damage = defender->unit.curHP - 1;"),
    Skill("Sturdy", "proc", "Sturdy", "Sturdy:[NL]If the unit has full HP at the[NL]start of the fight, they cannot die.",
          group="guard",
          after="if (gBattleStats.damage >= defender->unit.curHP && defender->hpInitial == defender->unit.maxHP\n"
                "            && SkillTesterFem(&defender->unit, SKILL_FEM_Sturdy)) {\n"
                "            gBattleStats.damage = defender->unit.curHP - 1;\n"
                "            ShowSkillFem(defender, SKILL_FEM_Sturdy);\n        }"),
    # lot 8: statuses inflicted on a hit, one at most (C-SkillSys's BattleHit_InjectNegativeStatus, in its order)
    Skill("Petrify", "proc", "Petrify", "Petrify:[NL]Inflict stone on the opponent.[NL](Skill % activation).",
          group="status", effect="if (status == -1 && allowed && SkillProcFem(attacker, SKILL_FEM_Petrify))\n"
                                 "            status = UNIT_STATUS_PETRIFY;"),
    Skill("Deadeye", "proc", "Deadeye", "Deadeye:[NL]Doubles hit rate and inflict sleep.[NL](Skill % activation).",
          group="status", roll="if (SkillProcFem(attacker, SKILL_FEM_Deadeye)) {\n"
                               "            sHitFlagsFem |= HIT_DEADEYE_FEM;\n            rate *= 2;\n        }",
          effect="if (status == -1 && allowed && (sHitFlagsFem & HIT_DEADEYE_FEM))\n"
                 "            status = UNIT_STATUS_SLEEP;"),
    Skill("PoisonPoint", "proc", "", "Poison Point:[NL]Inflict poison[NL]on the opponent.", group="status",
          effect="if (status == -1 && allowed && SkillTesterFem(&attacker->unit, SKILL_FEM_PoisonPoint))\n"
                 "            status = UNIT_STATUS_POISON;"),
    Skill("Enrage", "proc", "Enrage", "Enrage:[NL]Inflict Berserk on the opponent.[NL](Skill % activation).",
          group="status", effect="if (status == -1 && allowed && SkillProcFem(attacker, SKILL_FEM_Enrage))\n"
                                 "            status = UNIT_STATUS_BERSERK;"),
    Skill("EffectSpore", "proc", "EffectSpore",
          "Effect Spore:[NL]If attacked, 50% chance of inflicting[NL]poison, silence or sleep.", group="status",
          effect="if (status == -1 && allowed && !DebuffedFem(attacker)\n"
                 "            && SkillProcRateFem(defender, SKILL_FEM_EffectSpore, 50)) {\n"
                 "            static const u8 spores[] = { UNIT_STATUS_POISON, UNIT_STATUS_SILENCED, UNIT_STATUS_SLEEP };\n"
                 "            InjectStatusFem(attacker, spores[NextRN_N(3)], FALSE);\n            status = -2;\n        }"),
    Skill("BlackMagic", "proc", "BlackMagic",
          "Black Magic:[NL]Inflict a random bad status on the enemy.[NL](Skill % activation).", group="status",
          effect="if (status == -1 && allowed && SkillProcFem(attacker, SKILL_FEM_BlackMagic)) {\n"
                 "            static const u8 magics[] = { UNIT_STATUS_POISON, UNIT_STATUS_SLEEP, UNIT_STATUS_SILENCED,"
                 " UNIT_STATUS_BERSERK };\n"
                 "            status = magics[NextRN_N(4)];\n        }"),
    # lot 8: weapons and items (C-SkillSys's BattleHit_ConsumeWeapon, Pickup in BattleHit.c)
    Skill("Armsthrift", "proc", "Armsthrift", "Armsthrift:[NL]A weapon use is not consumed.[NL](Luck % activation).",
          group="items", effect="if (!keep && SkillProcRateFem(attacker, SKILL_FEM_Armsthrift, attacker->unit.lck))\n"
                                "            keep = TRUE;"),
    Skill("Corrosion", "proc", "Corrosion",
          "Corrosion:[NL]Reduce enemy's weapon durability[NL]by user's level (Skill % activation).", group="items",
          effect="if (hit && defender->weapon && SkillProcFem(attacker, SKILL_FEM_Corrosion)) {\n"
                 "            int uses = attacker->levelPrevious;\n\n"
                 "            while (uses-- > 0 && defender->weapon)\n"
                 "                defender->weapon = GetItemAfterUse(defender->weapon);\n"
                 "            if (!defender->weapon)\n                defender->weaponBroke = TRUE;\n        }"),
    Skill("Pickup", "proc", "",
          "Pickup: Obtain the last item in the[NL]enemy's inventory after attacking[NL]and killing them. (Luck %)",
          group="items",
          effect="if (hit && attacker == &gBattleActor && defender->unit.curHP == 0\n"
                 "            && SkillProcRateFem(attacker, SKILL_FEM_Pickup, attacker->unit.lck))\n"
                 "            defender->unit.state |= US_DROP_ITEM;"),
    # without an icon at the pinned commit (a "?" until FE Maker imports its own icons)
    _b("WatchfulEye", "battle", "Watchful Eye:[NL]Hit rate +20%.", "attacker->battleHitRate += 20;", icon=""),
    _b("HeavyStrikes", "weapon", "Heavy Strikes:[NL]Adds weapon weight[NL]to critical chance.",
       "attacker->battleCritRate += GetItemWeight(attacker->weapon);", icon=""),
    _b("KnightAspirant", "hp", "Knight Aspirant:[NL]Above 75% HP: +2 damage,[NL]+15% avoid.",
       "if (attacker->hpInitial * 4 > attacker->unit.maxHP * 3) {\n            attacker->battleAttack += 2;\n"
       "            attacker->battleAvoidRate += 15;\n        }", icon=""),
    _b("SilentPride", "hp", "Silent Pride:[NL]+2 damage and DEF per[NL]25% below max HP.",
       "{\n            int lost = (attacker->unit.maxHP - attacker->hpInitial) * 4 / attacker->unit.maxHP;\n\n"
       "            attacker->battleAttack += 2 * lost;\n            attacker->battleDefense += 2 * lost;\n        }",
       icon=""),
    _b("Frenzy", "hp", "Frenzy:[NL]For every 4 damage taken,[NL]+1 to damage dealt.",
       "attacker->battleAttack += (attacker->unit.maxHP - attacker->hpInitial) / 4;", icon=""),
    _b("Puissance", "foe", "Puissance:[NL]+3 Attack if attack is[NL]greater than the foe's.",
       "if (attacker->battleAttack > defender->battleAttack) attacker->battleAttack += 3;", kind="late", icon=""),
    _b("NoGuard", "hit", "No Guard:[NL]Both sides have a 100%[NL]chance of hitting.",
       "attacker->battleEffectiveHitRate = 100;", kind="eff", icon="", holder="either"),
    _b("WonderGuard", "guard", "Wonder Guard:[NL]No damage from weapons of[NL]the unit's weapon type.",
       "if (defender->weaponType == attacker->weaponType) attacker->battleAttack = 0;", kind="eff", icon="",
       holder="defender"),
    _b("CriticalPierce", "hit", "Critical Pierce:[NL]Ignores the foe's[NL]critical avoid.", "defender->battleDodgeRate = 0;",
       kind="late", icon=""),
    Skill("ShieldPulse", "proc", "", "Shield Pulse:[NL]Reduces damage from[NL]critical hits by 50%.", group="guard",
          after="if ((gBattleHitIterator->attributes & BATTLE_HIT_ATTR_CRIT)"
                " && SkillTesterFem(&defender->unit, SKILL_FEM_ShieldPulse))\n            decrease += DmgDecreaseFem(50);"),
    Skill("Gambit", "proc", "", "Gambit:[NL]Reduces critical damage[NL]taken in melee.", group="guard",
          after="if ((gBattleHitIterator->attributes & BATTLE_HIT_ATTR_CRIT) && gBattleStats.range == 1"
                " && SkillTesterFem(&defender->unit, SKILL_FEM_Gambit))\n"
                "            gBattleStats.damage = gBattleStats.damage * 5 / 6;"),
    Skill("MagicGambit", "proc", "", "Magic Gambit:[NL]Reduces critical damage[NL]taken at range.", group="guard",
          after="if ((gBattleHitIterator->attributes & BATTLE_HIT_ATTR_CRIT) && gBattleStats.range > 1"
                " && SkillTesterFem(&defender->unit, SKILL_FEM_MagicGambit))\n"
                "            gBattleStats.damage = gBattleStats.damage * 5 / 6;"),
    Skill("CounterRoar", "proc", "", "Counter Roar:[NL]-30% damage from the foe's[NL]first hit, -70% after.",
          group="guard", after="if (SkillTesterFem(&defender->unit, SKILL_FEM_CounterRoar))\n"
                               "            decrease += DmgDecreaseFem(HitRankFem(attacker) == 1 ? 30 : 70);"),
    Skill("CrusaderWard", "proc", "", "Crusader Ward:[NL]-80% damage from the foe's[NL]second ranged hit on.",
          group="guard", after="if (gBattleStats.range > 1 && HitRankFem(attacker) > 1"
                               " && SkillTesterFem(&defender->unit, SKILL_FEM_CrusaderWard))\n"
                               "            decrease += DmgDecreaseFem(80);"),
    # damage taken
    Skill("DragonSkin", "proc", "DragonSkin", "Dragon Skin:[NL]Halves damage taken.", group="guard",
          after="if (SkillTesterFem(&defender->unit, SKILL_FEM_DragonSkin))\n"
                "            decrease += DmgDecreaseFem(50);"),
    Skill("Multiscale", "proc", "Multiscale", "Multiscale:[NL]Halves damage taken[NL]if HP is full.", group="guard",
          after="if (defender->unit.curHP == defender->unit.maxHP && SkillTesterFem(&defender->unit, SKILL_FEM_Multiscale))\n"
                "            decrease += DmgDecreaseFem(50);"),
    Skill("Expertise", "proc", "Expertise", "Expertise:[NL]Halves damage taken[NL]from critical hits.", group="guard",
          after="if ((gBattleHitIterator->attributes & BATTLE_HIT_ATTR_CRIT)"
                " && SkillTesterFem(&defender->unit, SKILL_FEM_Expertise))\n"
                "            decrease += DmgDecreaseFem(50);"),
    Skill("Barricade", "proc", "Barricade", "Barricade:[NL]Halves damage taken once[NL]struck in this combat.",
          group="guard", after="if (defender->unit.curHP < defender->hpInitial"
                               " && SkillTesterFem(&defender->unit, SKILL_FEM_Barricade))\n"
                               "            decrease += DmgDecreaseFem(50);"),
    Skill("TowerShieldPlus", "proc", "TowerShieldPlus", "Tower Shield+:[NL]Takes no damage from[NL]attacks at range.",
          group="guard", after="if (gBattleStats.range > 1 && SkillTesterFem(&defender->unit, SKILL_FEM_TowerShieldPlus))\n"
                               "            gBattleStats.damage = 0;"),
    # batch 9, auras (C-SkillSys's PreBattleCalcAuraEffect, values from SkillExtraInfo.c; _aura_skills)
    _aura("DivinelyInspiring", "ally", 1, "D-Inspir: Adjacent allies[NL]deal +3 damage and[NL]receive -1 damage.",
          "attacker->battleAttack += 3;\n            attacker->battleDefense += 1;"),
    _aura("LilysPoise", "ally", 1, "Lily's Poise:[NL]Adjacent allies deal +1 damage[NL]and receive -3 damage.",
          "attacker->battleAttack += 1;\n            attacker->battleDefense += 3;"),
    _aura("BloodTide", "ally", 1, "Blood Tide:[NL]Grants +5 ATK and Hit[NL]to adjacent allies.",
          "attacker->battleAttack += 5;\n            attacker->battleHitRate += 5;"),
    _aura("WhitePool", "ally", 1, "White Pool:[NL]Grants +5 ATK and AS[NL]to adjacent allies.",
          "attacker->battleAttack += 5;\n            attacker->battleSpeed += 5;"),
    _aura("NightTide", "ally", 1, "Night Tide:[NL]Grants +5 DEF and RES[NL]to adjacent allies.",
          "attacker->battleDefense += 5;"),
    _aura("SpurStr", "ally", 1, "Spur Str:[NL]Adjacent allies gain +4 STR.",
          f"if (!{_MAGIC % 'attacker'}) attacker->battleAttack += 4;"),
    _aura("SpurMag", "ally", 1, "Spur Mag:[NL]Adjacent allies gain +4 MAG.",
          f"if ({_MAGIC % 'attacker'}) attacker->battleAttack += 4;"),
    _aura("SpurSpd", "ally", 1, "Spur Spd:[NL]Adjacent allies gain +4 SPD.", "attacker->battleSpeed += 4;"),
    _aura("SpurDef", "ally", 1, "Spur Def:[NL]Adjacent allies gain +4 DEF.",
          f"if (!{_MAGIC % 'defender'}) attacker->battleDefense += 4;"),
    _aura("SpurRes", "ally", 1, "Spur Res:[NL]Adjacent allies gain +4 RES.",
          f"if ({_MAGIC % 'defender'}) attacker->battleDefense += 4;"),
    _aura("Solidarity", "ally", 1, "Solidarity:[NL]+10 Crit and Crit Avoid[NL]to adjacent allies.",
          "attacker->battleCritRate += 10;\n            attacker->battleDodgeRate += 10;"),
    _aura("Charm", "ally", 2, "Charm: Allies within 2[NL]tiles deal +3 attack.", "attacker->battleAttack += 3;"),
    _aura("DriveStr", "ally", 2, "Drive Str:[NL]Allies within 2 tiles[NL]receive +4 STR.",
          f"if (!{_MAGIC % 'attacker'}) attacker->battleAttack += 4;"),
    _aura("DriveMag", "ally", 2, "Drive Mag:[NL]Allies within 2 tiles[NL]receive +4 MAG.",
          f"if ({_MAGIC % 'attacker'}) attacker->battleAttack += 4;"),
    _aura("DriveSpd", "ally", 2, "Drive Spd:[NL]Allies within 2 tiles[NL]receive +4 SPD.", "attacker->battleSpeed += 4;"),
    _aura("DriveDef", "ally", 2, "Drive Def:[NL]Allies within 2 tiles[NL]receive +4 DEF.",
          f"if (!{_MAGIC % 'defender'}) attacker->battleDefense += 4;"),
    _aura("DriveRes", "ally", 2, "Drive Res:[NL]Allies within 2 tiles[NL]receive +4 RES.",
          f"if ({_MAGIC % 'defender'}) attacker->battleDefense += 4;"),
    _aura("Inspiration", "ally", 2, "Inspir: Allies within 2 tiles[NL]deal +2 damage and[NL]receive -2 damage.",
          "attacker->battleAttack += 2;\n            attacker->battleDefense += 2;"),
    # C-SkillSys tests `UNIT_CATTRIBUTES(...) && CA_FEMALE` (always true): written after their descriptions
    _aura("Gentilhomme", "ally", 2, "Gentilhomme:[NL]Female allies within 2 tiles[NL]receive -2 damage.",
          "if (UNIT_CATTRIBUTES(&attacker->unit) & CA_FEMALE) attacker->battleDefense += 2;"),
    _aura("Demoiselle", "ally", 2, "Demoiselle:[NL]Male allies within 2 tiles[NL]receive -2 damage.",
          "if (!(UNIT_CATTRIBUTES(&attacker->unit) & CA_FEMALE)) attacker->battleDefense += 2;"),
    # Bond: +3 as its description (SkillExtraInfo.c says 2)
    _aura("Bond", "ally", 3, "Bond:[NL]+10 Hit, +3 damage to all[NL]allies within 3 tiles.",
          "attacker->battleAttack += 3;\n            attacker->battleHitRate += 10;"),
    _aura("Charisma", "ally", 3, "Charisma:[NL]Grants +10 Hit/Avoid to all[NL]allies within three tiles.",
          "attacker->battleHitRate += 10;\n            attacker->battleAvoidRate += 10;"),
    _aura("Hex", "foe", 1, "Hex:[NL]-15 Avoid to all[NL]adjacent enemies.", "attacker->battleAvoidRate -= 15;"),
    _aura("Intimidate", "foe", 2, "Intimidate:[NL]-10 Avoid to all[NL]enemies within 2 tiles.",
          "attacker->battleAvoidRate -= 10;"),
    _aura("VoiceOfPeace", "foe", 2, "V-Peace: Enemies within[NL]2 tiles deal -2 damage.", "attacker->battleAttack -= 2;"),
    _aura("Peacebringer", "both", 2, "Peacebringer:[NL]Allies and enemies within[NL]2 tiles deal -2 damage.",
          "attacker->battleAttack -= 2;"),
    _aura("MaleficAura", "foe", 2, "Malefic Aura:[NL]Enemies within 2 tiles[NL]receive +2 magic damage.",
          f"if ({_MAGIC % 'defender'}) attacker->battleDefense -= 2;"),
    _aura("Anathema", "foe", 3, "Anathema:[NL]-10 Avoid/Dodge to all[NL]enemies within 3 tiles.",
          "attacker->battleAvoidRate -= 10;\n            attacker->battleDodgeRate -= 10;"),
    _aura("Daunt", "foe", 3, "Daunt:[NL]-5 Hit and Crit to all enemy[NL]units in a 3-tile radius.",
          "attacker->battleHitRate -= 5;\n            attacker->battleCritRate -= 5;"),
    # the holder's own, by the units around it
    _aura("Tantivy", "self", 3, "Tantivy:[NL]+10 Hit/Avoid if there are[NL]no allies within 3 tiles.",
          "if (allies3 == 0) {\n            attacker->battleHitRate += 10;\n"
          "            attacker->battleAvoidRate += 10;\n        }"),
    _aura("Focus", "self", 3, "Focus:[NL]+10 Crit if there are[NL]no allies within 3 tiles.",
          "if (allies3 == 0) attacker->battleCritRate += 10;"),
    # batch 10: a real lord (C-SkillSys tests `UNIT_CATTRIBUTES(unit) && CA_LORD`: any ally), and Blue Flame's +2 next
    # to an ally that has it too, as its text says (C-SkillSys: next to any ally)
    _aura("Loyalty", "self", 2, "Loyalty:[NL]Within 2 spaces of a Lord,[NL]-3 damage taken, +15 Hit.",
          "if (lords2) {\n            attacker->battleHitRate += 15;\n            attacker->battleDefense += 3;\n        }"),
    _aura("BlueFlame", "self", 1, "Blue Flame:[NL]Attack +2; +2 more next[NL]to an ally with this skill.",
          "attacker->battleAttack += flames1 ? 4 : 2;"),
    _aura("Infiltrator", "self", 2, "Infilt: If within 2 spaces[NL]of two or more enemies,[NL]gain +3 damage and +15% Hit.",
          "if (foes2 >= 2) {\n            attacker->battleAttack += 3;\n            attacker->battleHitRate += 15;\n        }"),
    _aura("InnerFlame1", "self", 3, "Inner Flame: ATK +10 if[NL]no ally within 3 tiles.",
          "if (allies3 == 0) attacker->battleAttack += 10;"),
    _aura("InnerFlame2", "self", 2, "Inner Flame: ATK +7 if[NL]no ally within 2 tiles.",
          "if (allies2 == 0) attacker->battleAttack += 7;"),
    _aura("InnerFlame3", "self", 1, "Inner Flame: ATK +5 if[NL]no ally within 1 tile.",
          "if (allies1 == 0) attacker->battleAttack += 5;"),
)

# The game's class abilities, shown as skills: their engine stays the game's (texts written for FE8's own rules).
GAME_SKILLS: tuple[Skill, ...] = (
    Skill("Canto", "game", "Canto", "Canto:[NL]Unit can move again after[NL]acting.", game="UNIT_CATTRIBUTES(unit) & CA_CANTO"),
    Skill("Steal", "game", "Steal", "Steal:[NL]Unit can use the[NL]Steal command.", game="UNIT_CATTRIBUTES(unit) & CA_STEAL"),
    Skill("LockTouch", "game", "LockTouch", "Lock Touch:[NL]Opens doors and chests[NL]without keys.",
          game="UNIT_CATTRIBUTES(unit) & CA_THIEF"),
    Skill("Dance", "game", "Dance", "Dance:[NL]Unit can use the[NL]Dance command.",
          game="UNIT_CATTRIBUTES(unit) & (CA_DANCE | CA_PLAY)"),
    # the convoy: the route's lord (SupplyUsability, bmmenu.c); not CA_SUPPLY, FE7's convoy carrier (convoy.py)
    Skill("Supply", "game", "Supply", "Supply:[NL]Unit can use the[NL]Supply command.",
          game="unit->pCharacterData->number =="
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
MAGIC_SKILLS = frozenset(s.id for s in CATALOGUE if s.magic or (s.stats and all(k == 6 for k, _ in s.stats)))


def catalogue() -> list[dict]:
    """What FE Maker offers on the sheets (names and descriptions are UI strings: skill.<id>, skill.<id>Hint); Magic
    skills only with the Strength / Magic split."""
    return ([{"id": s.id, "kind": s.category, "magic": s.id in MAGIC_SKILLS} for s in CATALOGUE]
            + [{"id": sid, "kind": ASSIGNABLE_GROUP[sid], "magic": False} for sid in ASSIGNABLE])


# The game skills in FE Maker's words: the abilities (gamedata.ABILITIES) or the classes that give them
GAME_SOURCES = {"Canto": (["canto"], []), "Steal": (["steal"], []), "LockTouch": (["thiefSkills"], []),
                "Dance": (["dance", "play"], []), "Supply": ([], []), "Crit": (["critBonus"], []),
                "Lethality": (["lethality"], []), "Summon": (["summon"], []),
                "SureShot": ([], ["CLASS_SNIPER", "CLASS_SNIPER_F"]),
                "Pierce": ([], ["CLASS_WYVERN_KNIGHT", "CLASS_WYVERN_KNIGHT_F"]),
                "GreatShield": ([], ["CLASS_GENERAL", "CLASS_GENERAL_F"]),
                "Slayer": ([], ["CLASS_BISHOP", "CLASS_BISHOP_F"])}
GAME_CHARACTERS = {"Supply": ["CHARACTER_EIRIKA", "CHARACTER_EPHRAIM"]}   # the routes' lords


# Batch 4: the game abilities a sheet can give to anyone, by their class attribute: the game tests them everywhere
# (AI included) with UNIT_CATTRIBUTES, which then adds SkillAttributesFem (docs/competences.md)
# Supply has no attribute: the game's CA_SUPPLY is FE7's convoy carrier (convoy.py); the skill opens the convoy as the
# route's lord does, to the unit and the units next to it (SupplyUsability, ticket 46). Summon is not here: only the
# characters of gSummonConfig can summon; nor Magic Seal: the game looks for it on enemies only.
ASSIGNABLE = {"Canto": "CA_CANTO", "Steal": "CA_STEAL", "LockTouch": "CA_THIEF", "Crit": "CA_CRITBONUS",
              "Lethality": "CA_ASSASSIN", "Dance": "CA_DANCE", "Supply": ""}
# their category in the skill picker: that of what they do (ticket 26), not a "game abilities" one
ASSIGNABLE_GROUP = {"Canto": "map", "Steal": "menu", "LockTouch": "menu", "Crit": "hit", "Lethality": "hit",
                    "Dance": "menu", "Supply": "menu"}


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
    """The cached icon file, downloaded first if needed; a "?" for a skill C-SkillSys has no icon for."""
    skill = BY_ID.get(skill_id)
    if skill is None:
        raise SkillError("unknownSkill")
    if not skill.icon:
        return _placeholder()
    path = _download(ICON_URL.format(skill.icon), _cache() / f"{skill.icon}.png")
    return _retouched(skill.icon, path) if skill.icon in RETOUCHED else path


# Icons retouched so that all have the frame most of C-SkillSys's icons have (ticket 31): the stat bonuses' square grey
# frame replaced by it, and stray corner pixels made transparent. Their inside is left as drawn.
STANDARD_FRAME = (   # "." keeps the icon's pixel; else the palette index of the frame (Swap's and Canto's)
    "0001111111111900", "091..........190", "91............14", "1..............4", "1..............4",
    "1..............4", "1..............4", "1..............4", "1..............4", "1..............4",
    "1..............4", "1..............4", "1..............4", "21............40", "421..........400",
    "0444444444444000")
RETOUCHED = {**{f"{s}Bonus": "frame" for s in ("Str", "Mag", "Skl", "Spd", "Luk", "Def", "Res")},
             **{name: "corners" for name in ("FaireAxe", "FaireBMag", "FaireBow", "FaireLance", "FaireSword",
                                             "InfinityEdge", "StanceMirror")}}


def _retouched(icon: str, original: Path) -> Path:
    path = _cache().parent / "SkillIconFem" / f"{icon}.png"
    if path.is_file():
        return path
    from PIL import Image
    image = Image.open(original)
    pixels = image.load()
    for y, row in enumerate(STANDARD_FRAME):
        for x, ch in enumerate(row):
            corner = x in (0, 15) and y in (0, 15)
            if RETOUCHED[icon] == "frame" and ch != ".":
                pixels[x, y] = int(ch, 16)
            elif corner:
                pixels[x, y] = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, bits=4)
    return path


# The "?" icon of skills without one (FE Maker's own drawing, in the frame style of C-SkillSys's icons), in the
# game's item icon palette (0 transparent, 1 white, 2 light grey, 4 outline, 9 lavender)
PLACEHOLDER_ROWS = (
    "0001111111111900", "0919999999999190", "9199999999999914", "1499994444999924", "1499944994499924",
    "1499999994499924", "1499999944999924", "1499999449999924", "1499999449999924", "1499999999999924",
    "1499999449999924", "1499999449999924", "1999999999999294", "2199999999992940", "4212222222222400",
    "0444444444444000")
ICON_PALETTE = ((192, 248, 200), (248, 248, 248), (200, 192, 184), (144, 144, 128), (40, 56, 32), (216, 208, 32),
                (160, 8, 8), (56, 80, 240), (112, 120, 144), (176, 176, 208), (40, 128, 96), (104, 200, 184),
                (112, 80, 48), (152, 128, 112), (80, 56, 64), (192, 96, 0))


def _placeholder() -> Path:
    path = _cache() / "_placeholder.png"
    if not path.is_file():
        from PIL import Image
        image = Image.new("P", (16, 16))
        image.putpalette([c for rgb in ICON_PALETTE for c in rgb])
        image.putdata([int(ch, 16) for row in PLACEHOLDER_ROWS for ch in row])
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, bits=4)   # 4-bit like C-SkillSys's icons (gbagfx reads them as they are)
    return path


def box_png() -> bytes:
    """The box behind a triggered skill's name in battle (Huichelaar's ProcDisplayTiles, Skill System, CC0)."""
    return _download(BOX_URL, config_dir() / "skillsystem" / SS_COMMIT[:12] / "ProcDisplayTiles.png").read_bytes()


def seal_anim_png(name: str) -> bytes:
    """An image of the seals' animation (SEAL_ANIM_URLS), downloaded once from C-SkillSys."""
    return _download(SEAL_ANIM_URLS[name], _cache().parent / "MapAnim" / f"{name}.png").read_bytes()


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
    menus = [s for s in skills if s.menu]
    numbers = data.add_texts(LABEL, *PAGE_TEXTS, *(s.text.replace("[NL]", "[LF]\n") for s in skills),
                             *(f" {s.menu}[.]" for s in menus))   # as the game's: " Rescue[.]" (ticket 27)
    skill_numbers = numbers[1 + len(PAGE_TEXTS):1 + len(PAGE_TEXTS) + len(skills)]
    menu_numbers = numbers[1 + len(PAGE_TEXTS) + len(skills):]
    return {"label": numbers[0], "talk": numbers[1], "lead": numbers[2], "leadHelp": numbers[3],
            "leadValue": numbers[4], **{s.id: n for s, n in zip(skills, skill_numbers)},
            **{f"menu:{s.id}": n for s, n in zip(menus, menu_numbers)}}


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


def _raised(skills: list[Skill], magic_split: bool) -> list[int]:
    """The stats a skill raises or lowers, Magic only with the split (its getter exists only then)."""
    return sorted({k for s in skills for k, _ in s.stats if k != 6 or magic_split})


def apply(decomp_dir: Path, files: dict, characters: list[dict], classes: list[dict], texts: dict[str, int],
          magic_split: bool, extra=()) -> dict:
    """The skills into the overlay `files` (after strmag.apply). `texts`: add_texts's numbers; `extra`: event_skills."""
    skills = used(characters, classes, magic_split, extra)
    numbers = {s.id: i + 1 for i, s in enumerate(skills)}
    defines = "".join(f"#define SKILL_FEM_{s.id} {numbers[s.id]}\n" for s in skills)

    # bmunit.h: numbers and functions; the game abilities given by sheets or events added to UNIT_CATTRIBUTES
    rel = "include/bmunit.h"
    header = _read(files, decomp_dir, rel)
    abilities = [sid for sid in ASSIGNABLE if ASSIGNABLE[sid] and sid in given(characters, classes, extra)]
    supply = "Supply" in given(characters, classes, extra)
    if abilities:
        attributes = "#define UNIT_CATTRIBUTES(aUnit) ((aUnit)->pCharacterData->attributes | (aUnit)->pClassData->attributes)\n"
        header = _replace(header, attributes, (
            "int SkillAttributesFem(struct Unit* unit); /* FE Maker: game abilities given as skills */\n"
            "#define UNIT_CATTRIBUTES(aUnit) ((aUnit)->pCharacterData->attributes | (aUnit)->pClassData->attributes"
            " | SkillAttributesFem(aUnit))\n"), rel)
    # what changes with the skills used goes to its own header, included only by the files that use it (ticket 34: in
    # bmunit.h, adding a skill to a character recompiled ~266 files)
    files[NUMBERS_HEADER] = (
        "#ifndef GUARD_SKILLS_FEM_H\n#define GUARD_SKILLS_FEM_H\n\n"
        "/* FE Maker: the numbers of the skills this project uses (docs/competences.md) */\nstruct Unit;\n\n" + defines +
        f"#define SKILL_COUNT_FEM {len(skills)}\n"
        + "".join(f"int {GETTERS[k]}BaseFem(struct Unit* unit);\n" for k in _raised(skills, magic_split))
        + "\n#endif // GUARD_SKILLS_FEM_H\n")
    files[rel] = _replace(header, "\n#endif // GUARD_BM_UNIT_H", (
        "\n/* FE Maker: skills (docs/competences.md, from C-SkillSys); their numbers: skills_fem.h */\n#define SKILLS_FEM 1\n"
        f"extern const u8 gCharacterSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        f"extern const u8 gClassSkillsFem[0x100][{MAX_PER_SHEET}];\n"
        "int SkillTesterFem(struct Unit* unit, int skill);\nint SkillStatBonusFem(struct Unit* unit, int stat);\n"
        f"#define LEARNED_MAX_FEM {LEARNED_MAX}\n#define LEARNED_CHARACTERS_FEM 0x{LEARNED_CHARACTERS:X}\n"
        f"#define LEARNED_SKILLS_FEM ((u8 (*)[LEARNED_MAX_FEM]) {LEARNED_TABLE})\n"
        "void LearnSkillFem(struct Unit* unit, int skill);\nvoid ForgetSkillFem(struct Unit* unit, int skill);\n"
        "void LearnLevelSkillsFem(struct Unit* unit);\nvoid LearnedPopupsClearFem(void);\n"
        "void LearnedPopupsFem(void* proc);\n"
        "\n#endif // GUARD_BM_UNIT_H"), rel)

    # bmunit.c: tables, tester, stat bonuses, getters
    rel = "src/bmunit.c"
    unit = _read(files, decomp_dir, rel)
    char_rows = _table(decomp_dir, characters, numbers, "characters.h", "CHARACTER_NEW_")
    class_rows = _table(decomp_dir, classes, numbers, "classes.h", "CLASS_NEW_")
    bonuses = {k: [] for k in GETTERS}
    for s in skills:
        for k, value in s.stats:
            if k in _raised(skills, magic_split):
                cond = {"low": "defiant && ", "full": "full && ", "light": "!unit->items[3] && "}.get(s.when, "")
                bonuses[k].append(f"        if ({cond}SkillTesterFem(unit, SKILL_FEM_{s.id}))\n"
                                  f"            bonus += {value};\n")
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
             "    int defiant = unit->curHP * 4 < GetUnitMaxHp(unit);\n"
             "    int full = unit->curHP == GetUnitMaxHp(unit);\n\n"
             f"    switch (stat) {{\n{cases}    }}\n    (void) defiant;\n    (void) full;\n    return bonus;\n}}\n")
    if abilities:   # batch 4: on the lists only (SkillTesterFem), never through UNIT_CATTRIBUTES itself
        unit += ("\n/* Batch 4: the class attributes of the game abilities the unit has as skills */\n"
                 "int SkillAttributesFem(struct Unit* unit)\n{\n    int attributes = 0;\n\n"
                 + "".join(f"    if (SkillTesterFem(unit, SKILL_FEM_{sid}))\n        attributes |= {ASSIGNABLE[sid]};\n"
                           for sid in abilities)
                 + "    return attributes;\n}\n")
    if supply:   # ticket 46: the unit with Supply opens the convoy, to itself and to the units next to it
        rel_menu = "src/bmmenu.c"
        menu = _read(files, decomp_dir, rel_menu)
        phantom = "    if (gActiveUnit->pClassData->number == CLASS_PHANTOM)\n    {\n        return MENU_NOTSHOWN;\n    }\n"
        at = menu.index(phantom, menu.index("u8 SupplyUsability(")) + len(phantom)
        # the unit itself by its skills: the map of units leaves it out while it moves
        menu = (menu[:at] + "\n    if (SkillTesterFem(gActiveUnit, SKILL_FEM_Supply)"
                " || SupplySkillFem(gActiveUnit->xPos, gActiveUnit->yPos)) /* FE Maker: the Supply skill */\n"
                "    {\n        return MENU_ENABLED;\n    }\n" + menu[at:])
        files[rel_menu] = _replace(menu, "u8 SupplyUsability(", (
            "/* FE Maker: a player unit with the Supply skill on this square (ticket 46), next to the active one; no table:"
            " the link script drops"
            " this file's .rodata */\n"
            "static int SupplySkillAtFem(int x, int y)\n{\n    struct Unit* unit;\n\n"
            "    if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y || !gBmMapUnit[y][x])\n"
            "        return FALSE;\n"
            "    unit = GetUnit(gBmMapUnit[y][x]);\n"
            "    return UNIT_FACTION(unit) == FACTION_BLUE && SkillTesterFem(unit, SKILL_FEM_Supply);\n}\n\n"
            "static int SupplySkillFem(int x, int y)\n{\n"
            "    return SupplySkillAtFem(x + 1, y) || SupplySkillAtFem(x - 1, y)\n"
            "        || SupplySkillAtFem(x, y + 1) || SupplySkillAtFem(x, y - 1);\n}\n\nu8 SupplyUsability("), rel_menu)
    if "Dance" in abilities:   # ticket 46: only the dancer classes' battle animations can dance; others hang there
        rel_battle = "src/bmbattle.c"
        files[rel_battle] = _replace(_read(files, decomp_dir, rel_battle), "    if (sub_8055BC4()) {\n", (
            "    if (!((gBattleStats.config & BATTLE_CONFIG_REFRESH)\n"
            "        && !(gBattleActor.unit.pClassData->attributes & (CA_DANCE | CA_PLAY))) && sub_8055BC4()) {"
            " /* FE Maker: Dance as a skill, on the map; tested first, sub_8055BC4 already prepares the battle"
            " animation */\n"), rel_battle)
        # and on the map, the dancer classes' map sprites only have the dance frames (their animation 5): the others'
        # sprite would read past their animations and freeze the game
        rel_spell = "src/mapanim_spellassoc.c"
        switch = "    AP_SwitchAnimation(gManimSt.actor[gManimSt.subjectActorId].mu->sprite_anim, 0x5);\n"
        files[rel_spell] = _replace(_read(files, decomp_dir, rel_spell), switch, (
            "    if (gManimSt.actor[gManimSt.subjectActorId].unit->pClassData->attributes & (CA_DANCE | CA_PLAY))"
            " /* FE Maker: Dance as a skill */\n    " + switch), rel_spell)
    if "LockTouch" in abilities:   # ticket 28: the Rogue's Pick command too (C-SkillSys's Pick.c), no key needed
        rel_menu = "src/bmmenu.c"
        files[rel_menu] = _replace(_read(files, decomp_dir, rel_menu),
                                   "    if (gActiveUnit->pClassData->number != CLASS_ROGUE) {",
                                   "    if (gActiveUnit->pClassData->number != CLASS_ROGUE"
                                   " && !SkillTesterFem(gActiveUnit, SKILL_FEM_LockTouch)) { /* FE Maker: Lock Touch */",
                                   rel_menu)
    for k, name in GETTERS.items():   # only the stats a skill raises: their getter adds the bonus to the game's value
        if not bonuses[k]:
            continue
        head = f"int {name}(struct Unit* unit) {{"
        prefix = "inline " if f"inline {head}" in unit else ""
        unit = _replace(unit, prefix + head, (
            f"{prefix}{head}\n    int value = {name}BaseFem(unit) + SkillStatBonusFem(unit, {k});\n\n"
            f"    return value < 0 ? 0 : value; /* ticket 50: a malus never takes a stat under 0 */\n}}\n\n"
            f"int {name}BaseFem(struct Unit* unit) {{"), rel)
    files[rel] = unit
    if any(value < 0 for s in skills for _, value in s.stats):   # ticket 50: Fortress's -3 read "+7"
        show_malus(files, lambda rel_screen: _read(files, decomp_dir, rel_screen))

    # bmbattle.c: battle skills after the game's own computations, and the order of the rounds
    rel = "src/bmbattle.c"
    battle = _read(files, decomp_dir, rel)
    def skill_lines(kind):
        def test(s):
            if s.holder == "either":
                return (f"SkillTesterFem(&attacker->unit, SKILL_FEM_{s.id}) || "
                        f"SkillTesterFem(&defender->unit, SKILL_FEM_{s.id})")
            return f"SkillTesterFem(&{s.holder}->unit, SKILL_FEM_{s.id})"
        return "".join(f"    if ({test(s)})\n        {s.code}\n" for s in skills if s.kind == kind)
    # As C-SkillSys's PreBattleCalcInit: the actor's call computes both units' base stats, so that a skill can look
    # at the foe's; the target's call then only applies its skills (a target without class, as on the stat screen's
    # BattleGenerateUiStats, keeps the game's own order). Skills skip the arena and the stat screen, as C-SkillSys.
    start = "void ComputeBattleUnitStats(struct BattleUnit* attacker, struct BattleUnit* defender) {\n"
    battle = _replace(battle, start, (
        "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n"
        "static void ApplyBattleSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender)\n{\n"
        "    if (gBattleStats.config & (BATTLE_CONFIG_ARENA | BATTLE_CONFIG_BIT2))\n        return;\n"
        f"{skill_lines('battle')}    (void) defender;\n}}\n\n"
        "/* C-SkillSys's BattleCalcReal: skills comparing the unit with its foe, once both units' skills are applied */\n"
        "static void ApplyLateBattleSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender)\n{\n"
        "    if (gBattleStats.config & (BATTLE_CONFIG_ARENA | BATTLE_CONFIG_BIT2))\n        return;\n"
        f"{skill_lines('late')}    (void) defender;\n}}\n\n"
        "static void ComputeBattleUnitBaseStatsFem(struct BattleUnit* attacker, struct BattleUnit* defender) {\n"), rel)
    end = "    ComputeBattleUnitStatusBonuses(attacker);\n}\n"
    battle = _replace(battle, end, end + (
        "\n" + start +
        "    if (attacker == &gBattleActor) {\n"
        "        ComputeBattleUnitBaseStatsFem(attacker, defender);\n"
        "        if (defender == &gBattleTarget && gBattleTarget.unit.pClassData)\n"
        "            ComputeBattleUnitBaseStatsFem(defender, attacker);\n"
        "    } else if (attacker != &gBattleTarget || !attacker->unit.pClassData)\n"
        "        ComputeBattleUnitBaseStatsFem(attacker, defender);\n"
        "    ApplyBattleSkillsFem(attacker, defender);\n"
        + ("    ApplyAuraSkillsFem(attacker, defender);\n" if any(s.kind == "aura" for s in skills) else "")
        + "    ClampBattleStatsFem(attacker);\n}\n"), rel)
    if any(s.kind == "aura" for s in skills):
        battle = _replace(battle, start, _aura_function(skills) + start, rel)
    battle = _replace(battle, "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n", (
        "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n"
        "static void ClampBattleStatsFem(struct BattleUnit* bu)\n{\n"   # PreBattleCalcEnd
        + "".join(f"    if (bu->{f} < 0)\n        bu->{f} = 0;\n" for f in (
            "battleAttack", "battleDefense", "battleSpeed", "battleHitRate", "battleAvoidRate", "battleCritRate"))
        + "}\n\n"
        + (_OUTDOOR if any(s.id == "OutdoorFighter" for s in skills) else "")), rel)
    if any(s.kind == "eff" for s in skills):   # batch 6: hit and crit, after the game's effective rates
        special = "    ComputeBattleUnitSpecialWeaponStats(attacker, defender);\n}\n"
        battle = _replace(battle, special, special.replace("}\n", (
            "    if (!(gBattleStats.config & (BATTLE_CONFIG_ARENA | BATTLE_CONFIG_BIT2))) {\n"
            + skill_lines("eff") + "    }\n}\n")), rel)
    effective = "void ComputeBattleUnitEffectiveStats(struct BattleUnit* attacker, struct BattleUnit* defender) {\n"
    if any(s.kind == "late" for s in skills):
        battle = _replace(battle, effective, effective + (
            "    if (attacker == &gBattleActor) {\n"
            "        ApplyLateBattleSkillsFem(&gBattleActor, &gBattleTarget);\n"
            "        ApplyLateBattleSkillsFem(&gBattleTarget, &gBattleActor);\n"
            "        ClampBattleStatsFem(&gBattleActor);\n        ClampBattleStatsFem(&gBattleTarget);\n    }\n"), rel)
    # the triggered skills to show in battle (banim-main.c), cleared for each battle
    marker = "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n"
    battle = _replace(battle, marker, (
        f"#define sSkillShownFem ((vu8*) {SHOWN_SKILLS})\n#define SKILL_SHOWN_SIZE_FEM 0x{SHOWN_SIZE:X}\n\n" + marker), rel)
    order = any(s.kind == "order" or s.id in ORDER_EXTRA for s in skills)
    if order:
        battle = _battle_order(battle, numbers, rel)
        files["src/bksel.c"] = _forecast_order(_read(files, decomp_dir, "src/bksel.c"), "src/bksel.c")
    if any(s.kind in ("proc", "hits") for s in skills):
        battle = _hit_skills(battle, [s for s in skills if s.kind in ("proc", "hits")], rel)
    battle = _replace(battle, "void BattleUnwind(void) {\n    ClearBattleHits();\n",
                      "void BattleUnwind(void) {\n    ClearBattleHits();\n"
                      "    CpuFill16(0, (void*) sSkillShownFem, SKILL_SHOWN_SIZE_FEM);\n"
                      f"    CpuFill16(0, (void*) {STATUS_HITS}, BATTLE_HIT_MAX + 1);\n", rel)
    # an item's or a staff's map animation goes through the same rounds: without this, the last battle's skills
    # showed again when a unit used an item (ticket 48)
    battle = _replace(battle, "    gBattleTarget.statusOut = -1;\n\n    ClearBattleHits();\n}",
                      "    gBattleTarget.statusOut = -1;\n\n    ClearBattleHits();\n"
                      "    CpuFill16(0, (void*) sSkillShownFem, SKILL_SHOWN_SIZE_FEM); /* FE Maker (ticket 48) */\n"
                      f"    CpuFill16(0, (void*) {STATUS_HITS}, BATTLE_HIT_MAX + 1);\n}}", rel)
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
    files.update(_map_skills(decomp_dir, files, numbers))
    files.update(_post_action_skills(decomp_dir, files, numbers, base))
    files.update(_ai_skills(decomp_dir, files, numbers))
    files.update(_growth_skills(decomp_dir, files, numbers))
    if "Nullify" in numbers:   # batch 10: no effective weapon or class against the unit (C-SkillSys's CheckEffective.c)
        rel = "src/bmitem.c"
        text = _read(files, decomp_dir, rel)
        # after the declarations (C89)
        for head, who in (("s8 IsItemEffectiveAgainst(u16 item, struct Unit* unit) {\n", "unit"),
                          ("    const u8* effList = NULL;\n\n", "target")):
            text = _replace(text, head, head + f"    if (SkillTesterFem({who}, SKILL_FEM_Nullify)) /* FE Maker: Nullify */\n"
                            "        return FALSE;\n\n", rel)
        files[rel] = text
    bargains = [(sid, cost) for sid, cost in (("Bargain", "cost / 2"), ("Deal", "cost * 80 / 100")) if sid in numbers]
    if bargains:   # batch 10: C-SkillSys's Price.c, after the Silver Card, without stacking
        rel = "src/bmshop.c"
        files[rel] = _replace(_read(files, decomp_dir, rel), "        return (cost / 2);\n    else\n        return cost;\n",
                              "        return (cost / 2);\n" + "".join(
                                  f"    else if (SkillTesterFem(unit, SKILL_FEM_{sid})) /* FE Maker: {sid} */\n"
                                  f"        return {cost};\n" for sid, cost in bargains)
                              + "    else\n        return cost;\n", rel)
    if "Pass" in numbers:   # batch 10: through the foes' tiles (C-SkillSys's Movement.c, FMOVSTRE_PASS)
        rel = "src/bmidoten.c"
        files[rel] = _replace(_read(files, decomp_dir, rel),
                              "        gMovMapFillState.hasUnit = TRUE;\n        gMovMapFillState.unitId = unitId;\n",
                              "        gMovMapFillState.hasUnit = TRUE;\n        gMovMapFillState.unitId = unitId;\n"
                              "        if (SkillTesterFem(GetUnit(unitId), SKILL_FEM_Pass) /* FE Maker: Pass */\n"
                              "            && GetUnitCurrentHp(GetUnit(unitId)) * 4 >= GetUnitMaxHp(GetUnit(unitId)))\n"
                              "            gMovMapFillState.hasUnit = FALSE;\n", rel)
    files.update(_menu_skills(decomp_dir, files, numbers, texts))
    files.update(_learned(decomp_dir, files, _learn_table(decomp_dir, characters, numbers, "characters.h", "CHARACTER_NEW_"),
                          _learn_table(decomp_dir, classes, numbers, "classes.h", "CLASS_NEW_"), skills, numbers,
                          texts, base))
    return _include_numbers(files)


_STAT_BAR = "void DrawStatWithBar(int num, int x, int y, int base, int total, int max)\n{\n"
_MALUS_PALETTE = "    ApplyPalette(Pal_StatscreenEquipmentText, STATSCREEN_BGPAL_EQUIPMENT_LABEL);\n"
_MALUS_PATCHES = [
    ("src/fontgrp.c", "    if (number == 0)\n        return;\n\n",
     "    if (number == 0)\n        return;\n\n"
     "    if (number < 0) { /* FE Maker: a malus, drawn in the gray group (the status screen turns it red) */\n"
     "        PutSpecialChar(tm, TEXT_COLOR_SYSTEM_GRAY, TEXT_SPECIAL_DASH);\n"
     "        PutNumberSmall(tm + ((number <= -10) ? 2 : 1), TEXT_COLOR_SYSTEM_GRAY, -number);\n"
     "        return;\n    }\n\n"),
    # red: the gray group's colors 4-6 in a free palette (10), the bonus green's three colors (text palette 13-15:
    # main, highlight, shadow) turned red, so a malus looks like a bonus
    ("src/statscreen.c", _STAT_BAR,
     "/* FE Maker: a malus in red (ticket 50), palette 10 being free on this screen */\n"
     "#define STATSCREEN_BGPAL_MALUS_FEM 10\n"
     "static const u16 sMalusColorsFem[16] = { 0, 0, 0, 0, 0x18F8, 0x6F7F, 0x0C6B };\n\n" + _STAT_BAR),
    ("src/statscreen.c", _MALUS_PALETTE,
     _MALUS_PALETTE + "    ApplyPalette(sMalusColorsFem, STATSCREEN_BGPAL_MALUS_FEM); /* FE Maker: a malus in red */\n"),
    # "\n" first: the growth rates' branch (ticket 166) has the same call, further indented
    ("src/statscreen.c", "\n    DrawStatBarGfx(0x401 + num*6, 6,\n",
     "\n    if (diff < 0) { /* FE Maker: a malus in red, the bar shows the total */\n"
     "        u16* tm = gUiTmScratchA + TILEMAP_INDEX(x + 1, y);\n        int i;\n\n"
     "        for (i = 0; i <= (diff <= -10 ? 2 : 1); i++) {\n"
     "            tm[i] = (tm[i] & 0xFFF) | (STATSCREEN_BGPAL_MALUS_FEM << 12);\n"
     "            tm[i + 0x20] = (tm[i + 0x20] & 0xFFF) | (STATSCREEN_BGPAL_MALUS_FEM << 12);\n        }\n"
     "        base = total;\n        diff = 0;\n    }\n\n"
     "    DrawStatBarGfx(0x401 + num*6, 6,\n"),
]


def show_malus(files: dict, read) -> None:
    """The status screen shows a malus too, "-N" in red, the bar down to the total: the game draws bonuses only (a -3
    read "+7", ticket 50). For the items' temporary bonuses and the skills; written once. `read(rel)`: the file now."""
    for rel, old, new in _MALUS_PATCHES:
        text = read(rel)
        if new not in text:
            files[rel] = _replace(text, old, new, rel)


NUMBERS_HEADER = "include/skills_fem.h"
_NUMBERS_USE = re.compile(r"\bSKILL_FEM_\w+|\bSKILL_COUNT_FEM\b|\w+BaseFem\(")


def _include_numbers(files: dict) -> dict:
    """Ticket 34: each C file using the skills' numbers includes skills_fem.h, after its first include."""
    for rel, text in files.items():
        if not rel.endswith(".c") or not isinstance(text, str) or not _NUMBERS_USE.search(text):
            continue
        first = re.search(r'^#include "[^"]+"\n', text, re.M)
        line = f'#include "{NUMBERS_HEADER.removeprefix("include/")}" /* FE Maker: skills */\n'
        files[rel] = text[:first.end()] + line + text[first.end():] if first else line + text
    return files


DRAIN_FLAG = "0x02028D80"   # one byte after the icon table, in the same free RAM: Sol or Aether triggered on this hit
HIT_FLAGS = "0x02028D99"    # after the statuses of the hits: Deadeye (1) triggered on this hit
ASTRA_FLAG = "0x02028D81"   # the next one: Astra triggered in this battle (the attacker's hits are halved)
# then the triggered skills to show, 2 bytes per hit (the actor's, the target's), and the last round shown: 0x02028D82-91
SHOWN_SKILLS = "0x02028D82"
SHOWN_SIZE = 0x10
# then the status a skill inflicted on each hit (one byte per hit: the status, bit 7 when it is on the battle's target), shown
# by the battle animation's status flashing: 0x02028D92-98
STATUS_HITS = "0x02028D92"


def _hit_effects(battle: str, effects: str, rel: str) -> str:
    """Lot 8: what a hit leaves once its HP change is done (C-SkillSys's BattleHit_InjectNegativeStatus and
    BattleHit_ConsumeWeapon): one status at most, none against the Demon King or with a poison or stone weapon (the
    game's own); the weapon use kept by Armsthrift. Called where the game consumes the attacker's weapon."""
    battle = _replace(battle, "void BattleGenerateHitEffects(struct BattleUnit* attacker, struct BattleUnit* defender) {\n",
                      """/* FE Maker: a status inflicted by a skill (C-SkillSys's InjectNegativeStatusExt); foe: on the hit's
   defender (the game's own poison and stone effects), else on its attacker (Effect Spore) */
#define sStatusHitFem ((vu8*) """ + STATUS_HITS + """)

static void InjectStatusFem(struct BattleUnit* bu, int status, int foe)
{
    int old = bu->statusOut >= 0 ? bu->statusOut : bu->unit.statusIndex;
    int hit = gBattleHitIterator - gBattleHitArray;

    if (old == UNIT_STATUS_PETRIFY || old == UNIT_STATUS_13)
        bu->unit.state &= ~US_UNSELECTABLE;   /* "ungray" a petrified unit, as the game's poison does */
    bu->statusOut = status;
    if (status == UNIT_STATUS_PETRIFY) {
        if (UNIT_FACTION(&bu->unit) == gPlaySt.faction)
            bu->statusOut = UNIT_STATUS_13;
        gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_PETRIFY;
        return;
    }
    if (status == UNIT_STATUS_POISON && foe)
        gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_POISON;
    /* the battle animation flashes the unit in its status's color from this hit on (banim-ekrutils.c) */
    if (hit >= 0 && hit < BATTLE_HIT_MAX)
        sStatusHitFem[hit] = status | (bu == &gBattleTarget ? 0x80 : 0);
}

static int DebuffedFem(struct BattleUnit* bu)
{
    int status = bu->statusOut >= 0 ? bu->statusOut : bu->unit.statusIndex;

    return (status >= UNIT_STATUS_POISON && status <= UNIT_STATUS_BERSERK) || status >= UNIT_STATUS_PETRIFY;
}

/* TRUE: the weapon use is kept */
static int ApplyHitEffectSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender)
{
    int hit = !(gBattleHitIterator->attributes & BATTLE_HIT_ATTR_MISS);
    int effect = GetItemWeaponEffect(attacker->weapon);
    int allowed = hit && defender->unit.pClassData->number != CLASS_DEMON_KING
        && effect != WPN_EFFECT_POISON && effect != WPN_EFFECT_PETRIFY;
    int status = -1, keep = FALSE;

""" + effects + """    if (status >= 0)
        InjectStatusFem(defender, status, TRUE);
    (void) DebuffedFem; (void) hit; (void) allowed;
    return keep;
}

void BattleGenerateHitEffects(struct BattleUnit* attacker, struct BattleUnit* defender) {
""", rel)
    use = ("    if (!(gBattleHitIterator->attributes & BATTLE_HIT_ATTR_MISS) || "
           "attacker->weaponAttributes & (IA_UNCOUNTERABLE | IA_MAGIC)) {\n        attacker->weapon = GetItemAfterUse(")
    return _replace(battle, use, (
        "    if ((!(gBattleHitIterator->attributes & BATTLE_HIT_ATTR_MISS) || "
        "attacker->weaponAttributes & (IA_UNCOUNTERABLE | IA_MAGIC))\n"
        "        && !ApplyHitEffectSkillsFem(attacker, defender)) { /* FE Maker: skills (lot 8) */\n"
        "        attacker->weapon = GetItemAfterUse("), rel)


def _hit_skills(battle: str, procs: list[Skill], rel: str) -> str:
    """Skills that trigger on a hit, Skill % of the time (C-SkillSys's CheckBattleSkillActivate, never in the forecast):
    before the damage (defense, attack, Pavise and Aegis as the game's Great Shield, Luna and Corona as its Pierce),
    after the critical roll (Colossus, shown as a critical hit), and the HP drain of Sol and Aether, as Nosferatu's."""
    hits = [s for s in procs if s.kind == "hits"]
    ids = {s.id for s in procs}
    before = "".join(f"    {{\n        {s.code}\n    }}\n" for s in procs if s.kind == "proc" and s.code)
    rolls = "".join(f"    {{\n        {s.roll}\n    }}\n" for s in procs if s.roll)
    # C-SkillSys's CheckSkillActivateExt: Rightful King and God, Hero (under half HP) raise the rate of all the unit's
    bonus = "".join(line for sid, line in (
        ("RightfulKing", "    if (SkillTesterFem(&unit->unit, SKILL_FEM_RightfulKing))\n        rate += 10;\n"),
        ("RightfulGod", "    if (SkillTesterFem(&unit->unit, SKILL_FEM_RightfulGod))\n        rate += 30;\n"),
        ("Hero", "    if (SkillTesterFem(&unit->unit, SKILL_FEM_Hero) && unit->unit.curHP * 2 < unit->unit.maxHP)\n"
                 "        rate += 30;\n")) if sid in ids)
    counters = "".join(line for sid, line in (
        ("Counter", "    if (SkillTesterFem(&defender->unit, SKILL_FEM_Counter) && gBattleStats.range == 1 && !magic) {\n"
                    "        ShowSkillFem(defender, SKILL_FEM_Counter);\n        return TRUE;\n    }\n"),
        ("CounterMagic", "    if (SkillTesterFem(&defender->unit, SKILL_FEM_CounterMagic)"
                         " && gBattleStats.range >= 2 && magic) {\n"
                         "        ShowSkillFem(defender, SKILL_FEM_CounterMagic);\n        return TRUE;\n    }\n"))
        if sid in ids)
    # C-SkillSys's CheckDevilAttack after the counters, on the game's Devil roll (31 - the attacker's Luck): Devil's Luck
    # (the defender's Devil weapon hurts the attacker, the holder's own spares it), Devil's Pact, Devil's Whim
    devils = [sid for sid in ("DevilsLuck", "DevilsPact", "DevilsWhim") if sid in ids]
    luck = ("SkillTesterFem(&defender->unit, SKILL_FEM_DevilsLuck)"
            " && GetItemWeaponEffect(defender->weapon) == WPN_EFFECT_DEVIL")
    tests = {"DevilsLuck": [("defender", luck)],
             "DevilsPact": [("defender", "SkillTesterFem(&defender->unit, SKILL_FEM_DevilsPact)")],
             "DevilsWhim": [("defender", "SkillTesterFem(&defender->unit, SKILL_FEM_DevilsWhim)"),
                            ("attacker", "SkillTesterFem(&attacker->unit, SKILL_FEM_DevilsWhim)")]}
    devil_any = "".join(f"    if ({test})\n        other = TRUE;\n" for sid in devils for _who, test in tests[sid])
    devil_luck = ("    if (" + luck + ") {\n        ShowSkillFem(defender, SKILL_FEM_DevilsLuck);\n        return TRUE;\n    }\n"
                  "    if (devil && SkillTesterFem(&attacker->unit, SKILL_FEM_DevilsLuck))\n        return FALSE;\n"
                  if "DevilsLuck" in devils else "")
    devil_rest = "".join(f"    if ({test}) {{\n        ShowSkillFem({who}, SKILL_FEM_{sid});\n        return TRUE;\n    }}\n"
                         for sid in devils if sid != "DevilsLuck" for who, test in tests[sid])
    more = "".join(f"    {{\n        {s.code}\n    }}\n" for s in hits)
    after = "".join(f"    {{\n        {s.after}\n    }}\n" for s in procs if s.after)
    battle = _replace(battle, "/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */\n", f"""\
/* FE Maker: skills that trigger on a hit (C-SkillSys: SkillActRate.c, SkillEffects/BattleDamage) */
#define sHitDrainFem (*(vu8*) {DRAIN_FLAG})
#define sAstraFem (*(vu8*) {ASTRA_FLAG})
#define sHitFlagsFem (*(vu8*) {HIT_FLAGS})
#define HIT_DEADEYE_FEM 1

/* the skill's name is shown with this hit (2 bytes per hit: the actor's skill, the target's) */
static void ShowSkillFem(struct BattleUnit* unit, int skill)
{{
    if (gBattleHitIterator < gBattleHitArray + BATTLE_HIT_MAX)
        sSkillShownFem[(gBattleHitIterator - gBattleHitArray) * 2 + (unit == &gBattleTarget)] = skill;
}}

static int SkillProcRateFem(struct BattleUnit* unit, int skill, int rate)
{{
    if (gBattleStats.config & BATTLE_CONFIG_SIMULATE)
        return FALSE;
    if (!SkillTesterFem(&unit->unit, skill))
        return FALSE;
{bonus}    if (!BattleRoll2RN(rate, FALSE))
        return FALSE;
    ShowSkillFem(unit, skill);
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

/* Deadeye: the hit rate of this hit */
static int HitRateSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender, int rate)
{{
{rolls}    (void) defender;
    return rate;
}}
/* Counter, Counter Magic, then the game's Devil roll for a Devil weapon and Devil's Luck, Pact and Whim (C-SkillSys's
   CheckDevilAttack): the hit's damage goes back to its attacker */
static int DevilFem(struct BattleUnit* attacker, struct BattleUnit* defender)
{{
    int magic = attacker->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE);
    int devil = GetItemWeaponEffect(attacker->weapon) == WPN_EFFECT_DEVIL;
    int other = FALSE;

{counters}{devil_any}    if (!devil && !other)
        return FALSE;
    if (!BattleRoll1RN(31 - attacker->unit.lck, FALSE))
        return FALSE;
{devil_luck}    if (devil)
        return TRUE;
{devil_rest}    (void) magic;
    return FALSE;
}}
static void ApplyHitSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender, short* attack, short* defense)
{{
    int magic = attacker->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE);

{before}    (void) magic; (void) attack; (void) defense;
}}

/* C-SkillSys's _DmgDecreaseRef: damage reductions add up, damage * 0x100 / (0x100 + their sum) */
static int DmgDecreaseFem(int rate)
{{
    return 0x100 * rate / (100 - rate);
}}

/* The attacker's hits so far in this battle, this one included (C-SkillSys's round_cnt_hit) */
static int HitRankFem(struct BattleUnit* unit)
{{
    struct BattleHit* hit;
    int rank = 1;

    for (hit = gBattleHitArray; hit < gBattleHitIterator; hit++)
        if (!(hit->info & BATTLE_HIT_INFO_RETALIATION) == (unit == &gBattleActor))
            rank++;
    return rank;
}}

static void ApplyHitSkillsAfterFem(struct BattleUnit* attacker, struct BattleUnit* defender)
{{
    int decrease = 0;

{after}    if (decrease > 0 && gBattleStats.damage > 0) {{
        gBattleStats.damage = gBattleStats.damage * 0x100 / (0x100 + decrease);
        if (gBattleStats.damage == 0)
            gBattleStats.damage = 1;
    }}
    (void) defender; (void) HitRankFem;
}}

/* FE Maker: skills in battle (C-SkillSys, PreBattleCalc.c) */
""", rel)
    battle = _replace(battle, "    gBattleStats.damage = 0;\n\n    BattleCheckSureShot(attacker);\n",
                      "    gBattleStats.damage = 0;\n    sHitDrainFem = FALSE;\n    sHitFlagsFem = 0;\n\n"
                      "    BattleCheckSureShot(attacker);\n", rel)
    if rolls:
        battle = _replace(battle, "        if (!BattleRoll2RN(gBattleStats.hitRate, TRUE)) {\n",
                          "        if (!BattleRoll2RN(HitRateSkillsFem(attacker, defender, gBattleStats.hitRate), TRUE)) {\n",
                          rel)
    if counters or devils:
        battle = _replace(battle, "        if ((GetItemWeaponEffect(attacker->weapon) == WPN_EFFECT_DEVIL)"
                          " && (BattleRoll1RN(31 - attacker->unit.lck, FALSE))) {\n",
                          "        if (DevilFem(attacker, defender)) {\n", rel)
    battle = _replace(battle, "        defense = 0;\n\n    gBattleStats.damage = attack - defense;\n",
                      "        defense = 0;\n\n    ApplyHitSkillsFem(attacker, defender, &attack, &defense);\n\n"
                      "    gBattleStats.damage = attack - defense;\n", rel)
    cap = ("    if (gBattleStats.damage > BATTLE_MAX_DAMAGE)\n        gBattleStats.damage = BATTLE_MAX_DAMAGE;\n\n"
           "    if (gBattleStats.damage < 0)\n        gBattleStats.damage = 0;\n\n    BattleCheckPetrify(")
    battle = _replace(battle, cap, "    ApplyHitSkillsAfterFem(attacker, defender);\n\n" + cap, rel)
    effects = "".join(f"    {{\n        {s.effect}\n    }}\n" for s in procs if s.effect)
    if effects:
        battle = _hit_effects(battle, effects, rel)
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
#include "efxbattle.h"

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

/* When a hit lands (banim-ekrutils.c): the status a skill inflicted on it flashes its unit in the status's color, as the
   game does for a poison weapon's target; also on the hit's attacker (Effect Spore), sleep, silence and berserk */
void StatusHitFem(struct Anim* anim, struct Anim* foe)
{{
    int round = anim->nextRoundId - 1, status, target;
    struct Anim* who;

    if (round < 0 || round >= BATTLE_HIT_MAX || ((vu8*) {STATUS_HITS})[round] == 0)
        return;
    status = ((vu8*) {STATUS_HITS})[round] & 0x7F;
    target = ((vu8*) {STATUS_HITS})[round] >> 7;
    /* is anim the battle's target's? */
    who = ((GetAnimPosition(anim) == POS_L) != (gpEkrBattleUnitLeft == &gBattleActor)) == target ? anim : foe;
    if (GetUnitEfxDebuff(who) == UNIT_STATUS_NONE)
        SetUnitEfxDebuff(who, status);
}}

/* A hit that drains HP (Sol, Aether; banim-ekrutils.c): its HP bars as Nosferatu's, the foe's then the attacker's
   (ticket 44: else the attacker's healing was never shown and its next HP values came one step late) */
int DrainHitFem(struct Anim* anim)
{{
    int round = anim->nextRoundId - 1;

    return round >= 0 && round < BATTLE_HIT_MAX && (gBattleHitArray[round].attributes & BATTLE_HIT_ATTR_HPSTEAL);
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
    rel = "src/banim-ekrutils.c"
    start = "void StartBattleAnimHitEffects(struct Anim *anim, int type, int a, int b)\n{"
    utils = _replace(_read(files, decomp_dir, rel), start,
                     "void StatusHitFem(struct Anim* anim, struct Anim* foe); /* FE Maker: skills.py, in bmbattle.c */\n"
                     "int DrainHitFem(struct Anim* anim);\nvoid NewEfxHpBarDrainFem(struct Anim* anim);\n\n"
                     + start, rel)
    utils = _replace(utils, "    case EKR_HITTED:\n        roundt1 = GetRoundFlagByAnim(animr7);\n",
                     "    case EKR_HITTED:\n        StatusHitFem(anim, animr7); /* FE Maker: skills */\n"
                     "        roundt1 = GetRoundFlagByAnim(animr7);\n", rel)
    out[rel] = _replace(utils, "        if (val1 != val2) {\n            NewEfxHpBar(animr5);\n",
                        "        if (val1 != val2) {\n"
                        "            if (DrainHitFem(anim)) /* FE Maker: Sol, Aether (ticket 44) */\n"
                        "                NewEfxHpBarDrainFem(animr5);\n"
                        "            else\n"
                        "                NewEfxHpBar(animr5);\n", rel)
    out.update(_drain_bars(decomp_dir, files))
    return out


def _drain_bars(decomp_dir: Path, files: dict) -> dict:
    """Ticket 44: a drain without Nosferatu (Sol, Aether) uses Nosferatu's HP bars: the foe's falls, then the attacker's
    rises with the healing sound; without Nosferatu's wait for its spell (0x54 frames), which paused the battle: the
    attacker's bar starts as soon as the foe's stops, as C-SkillSys's BanimHpDrainFix (Mokha). The script is a copy of
    the game's as it is in the file (with the battle numbers' step when that option is on)."""
    rel = "src/banim-efxhpbar.c"
    bar = _read(files, decomp_dir, rel)
    start = bar.find("CONST_DATA struct ProcCmd ProcScr_EfxHpBarResire[] = {\n")
    if start < 0:
        raise SkillError(f"Skills: {rel} does not match this version of the decomp (efxHPBarResire)")
    script = bar[start:bar.index("};\n", start) + 3]
    wait = "    PROC_REPEAT(EfxHpBarResire_WaitOnCurrentSide),\n"
    if script.count(wait) != 1:
        raise SkillError(f"Skills: {rel} does not match this version of the decomp (efxHPBarResire)")
    script = (script.replace("CONST_DATA struct ProcCmd ProcScr_EfxHpBarResire[]",
                             "static const struct ProcCmd ProcScr_EfxHpBarDrainFem[]")
              .replace('PROC_NAME("efxHPBarResire")', 'PROC_NAME("efxHPBarDrainFem")')
              .replace(wait, "    PROC_REPEAT(EfxHpBarDrainWaitFem),\n"))
    return {rel: bar + """
/* FE Maker (skills.py, ticket 44): Sol's and Aether's HP bars, Nosferatu's without its spell's wait (C-SkillSys) */
static void EfxHpBarDrainWaitFem(struct ProcEfxHpBar * proc)
{
    if (proc->finished == false)
    {
        if (++proc->timer == 2)
        {
            proc->timer = 0;
            proc->cur += proc->diff;
            gEkrGaugeHp[GetAnimPosition(proc->anim_main_this)] += proc->diff;

            if (proc->cur == proc->next)
                proc->finished = true;
        }
    }

    if (proc->finished == true)
    {
        gEfxHpLutOff[GetAnimPosition(proc->anim_main_this)]++;
        gEkrHitNow[GetAnimPosition(proc->anim_main_this)] = 0;

        if (proc->next == 0)
            proc->death = true;

        proc->timer = 0;
        proc->cur = 10;
        gEfxHpBarResireFlag = 1;

        Proc_Break(proc);
        return;
    }
}

""" + script + """
void NewEfxHpBarDrainFem(struct Anim * anim)
{
    ProcPtr proc;

    if (gEkrHpBarCount != 0)
        return;
    NewEfxHpBarResire(anim);
    proc = Proc_Find(ProcScr_EfxHpBarResire);
    if (proc)
        Proc_GotoScript(proc, ProcScr_EfxHpBarDrainFem);
}
"""}


MENU_SKILL = "0x02028E3C"   # free RAM after Galeforce's: the menu command whose targets are being listed

# The unit menu's moving commands (C-SkillSys's HerosMovement): for a target ally at (tx, ty) next to the unit at
# (ux, uy), the unit that moves (`unit` the ally, else the active unit) and where to: (x, y). Swap moves both.
MOVES = {
    "Pivot": ("gSubjectUnit", "2 * tx - ux", "2 * ty - uy"),
    "Reposition": ("unit", "2 * ux - tx", "2 * uy - ty"),
    "Shove": ("unit", "2 * tx - ux", "2 * ty - uy"),
    "Swap": ("unit", "ux", "uy"),
    "Smite": ("unit", "3 * tx - 2 * ux", "3 * ty - 2 * uy"),
}
# Rally (C-SkillSys's Rally.c): the stats (gamedata.TEMP_STATS) raised by 4 for the allies within 2 tiles, on the
# temporary bonuses' counters (Magic's, the 7th, only with the Strength / Magic split; none for Movement)
RALLIES = {"RallyStrength": (0,), "RallyMagic": (6,), "RallySkill": (1,),
           "RallySpeed": (2,), "RallyLuck": (5,), "RallyDefense": (3,),
           "RallyResistance": (4,), "RallySpectrum": (0, 1, 2, 3, 4, 5, 6)}


def _menu_skills(decomp_dir: Path, files: dict, numbers: dict[str, int], texts: dict[str, int]) -> dict:
    """Batch 4, commands of the unit menu (before Rescue), each only when the project uses it (C-SkillSys's
    HerosMovement: Pivot.c, Reposition.c, Shove.c, Swap.c): Pivot (to the other side of an adjacent ally),
    Reposition (the ally to the other side of the unit), Shove (the ally one tile further), Swap (the unit and the
    ally switch places). The units slide there on the map (ticket 27); then the unit waits."""
    rallies = [sid for sid in RALLIES if sid in numbers]
    used = [sid for sid in MOVES if sid in numbers] + rallies
    if not used:
        return {}
    out = {}
    rel = "src/menu_def.c"
    out[rel] = _replace(_read(files, decomp_dir, rel), "CONST_DATA struct MenuItemDef gUnitActionMenuItems[] = {\n", (
        "".join(f"u8 {sid}UsabilityFem(const struct MenuItemDef* def, int number); /* FE Maker: skills */\n"
                f"u8 {sid}EffectFem(struct MenuProc* menu, struct MenuItemProc* menuItem);\n" for sid in used)
        + "\nCONST_DATA struct MenuItemDef gUnitActionMenuItems[] = {\n"), rel)
    entries = "".join(
        f"    {{\"　{BY_ID[sid].menu}\", {texts['menu:' + sid]}, {texts[sid]}, 0, {0x6A + i}, {sid}UsabilityFem, 0, "
        f"{sid}EffectFem, 0, 0, 0}}, // FE Maker: {sid}\n" for i, sid in enumerate(used))
    out[rel] = _replace(out[rel], "    {\"　救出\", 0x689,", entries + "    {\"　救出\", 0x689,", rel)
    if "Reposition" in used or rallies:   # the longest names: one more tile for the menu (ticket 27)
        out[rel] = _replace(out[rel], "CONST_DATA struct MenuDef gUnitActionMenuDef = {\n    {1, 3, 7, 0},",
                            "CONST_DATA struct MenuDef gUnitActionMenuDef = {\n    {1, 3, 8, 0},", rel)
    cases = "".join(f"""\
        case SKILL_FEM_{sid}:
            mover = {mover};
            x = {x};
            y = {y};
            break;
""" for sid, (mover, x, y) in MOVES.items() if sid in used)
    commands = "".join(f"""
u8 {sid}UsabilityFem(const struct MenuItemDef* def, int number)
{{
    return MoveSkillUsabilityFem(SKILL_FEM_{sid});
}}

u8 {sid}EffectFem(struct MenuProc* menu, struct MenuItemProc* menuItem)
{{
    return MoveSkillEffectFem(SKILL_FEM_{sid});
}}
""" for sid in used if sid in MOVES) + "".join(f"""
u8 {sid}UsabilityFem(const struct MenuItemDef* def, int number)
{{
    return RallyUsabilityFem(SKILL_FEM_{sid});
}}

u8 {sid}EffectFem(struct MenuProc* menu, struct MenuItemProc* menuItem)
{{
    return RallyEffectFem(0x{sum(4 << (4 * stat) for stat in RALLIES[sid]):X});
}}
""" for sid in rallies)
    rally = """
/* Rally (C-SkillSys's Rally.c): +4 on the temporary bonuses' counters (as a drink: game option tempBonusRule) of the
   allies within 2 tiles, dropping by 1 at each of their phases; then the unit waits */
static int RallyTargetFem(struct Unit* unit)
{
    int d;

    if (!unit || !unit->pCharacterData || unit == gActiveUnit || !AreUnitsAllied(gActiveUnit->index, unit->index)
        || unit->state & (US_HIDDEN | US_DEAD | US_RESCUED | US_NOT_DEPLOYED | US_BIT16))
        return FALSE;
    d = (unit->xPos > gActiveUnit->xPos ? unit->xPos - gActiveUnit->xPos : gActiveUnit->xPos - unit->xPos)
        + (unit->yPos > gActiveUnit->yPos ? unit->yPos - gActiveUnit->yPos : gActiveUnit->yPos - unit->yPos);
    return d <= 2;
}

static u8 RallyUsabilityFem(int skill)
{
    int i;

    if (gActiveUnit->state & US_CANTOING || !SkillTesterFem(gActiveUnit, skill))
        return MENU_NOTSHOWN;
    for (i = 1; i < 0xC0; i++)
        if (RallyTargetFem(GetUnit(i)))
            return MENU_ENABLED;
    return MENU_NOTSHOWN;
}

static u8 RallyEffectFem(u32 values)
{
    int i;

    for (i = 1; i < 0xC0; i++) {
        struct Unit* unit = GetUnit(i);

        if (RallyTargetFem(unit))
            SET_TEMP_BONUSES_FEM(unit, TempBonusesAfterFem(unit, values, values));
    }
    gActionData.xMove = gActiveUnit->xPos;
    gActionData.yMove = gActiveUnit->yPos;
    gActionData.unitActionType = UNIT_ACTION_WAIT;
    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}
""" if rallies else ""
    rel = "src/bmmenu.c"
    out[rel] = _read(files, decomp_dir, rel) + f"""
/* FE Maker, skills batch 4: the unit menu's moving commands (C-SkillSys, HerosMovement: Pivot.c, Reposition.c,
   Shove.c, Swap.c) */
#define sMoveSkillFem (*(vu8*) {MENU_SKILL})
s8 CanUnitCrossTerrain(struct Unit* unit, int terrain);
void ForEachAdjacentUnit(int x, int y, void(*func)(struct Unit* unit));
s8 AreUnitsAllied(int left, int right);
void RefreshUnitSprites(void);
int GetFacingDirection(int xPos, int yPos, int xLook, int yLook);
void HideUnitSprite(struct Unit* unit);

/* Where the command sends the unit that moves (FALSE: nowhere it can stand) */
static int MoveSkillDestinationFem(struct Unit* unit, int ux, int uy, struct Unit** moverOut, int* xOut, int* yOut)
{{
    int tx = unit->xPos;
    int ty = unit->yPos;
    struct Unit* mover = unit;
    int x = ux;
    int y = uy;

    switch (sMoveSkillFem)
    {{
{cases}    }}
    if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
        return FALSE;
    if (gBmMapUnit[y][x] != 0 && !(x == ux && y == uy))
        return FALSE;
    if (!CanUnitCrossTerrain(mover, gBmMapTerrain[y][x]))
        return FALSE;
    if (mover == unit && x == ux && y == uy && !CanUnitCrossTerrain(gSubjectUnit, gBmMapTerrain[ty][tx]))
        return FALSE;   /* Swap: the unit must stand on the ally's tile too */
    *moverOut = mover;
    *xOut = x;
    *yOut = y;
    return TRUE;
}}

static void TryAddMoveSkillTargetFem(struct Unit* unit)
{{
    struct Unit* mover;
    int x, y;

    if (!AreUnitsAllied(gSubjectUnit->index, unit->index) || unit->state & (US_HIDDEN | US_DEAD | US_RESCUED))
        return;
    if (MoveSkillDestinationFem(unit, gSubjectUnit->xPos, gSubjectUnit->yPos, &mover, &x, &y))
        AddTarget(unit->xPos, unit->yPos, unit->index, 0);
}}

static void MakeMoveSkillTargetListFem(struct Unit* unit, int skill)
{{
    sMoveSkillFem = skill;
    gSubjectUnit = unit;
    BmMapFill(gBmMapRange, 0);
    InitTargets(unit->xPos, unit->yPos);
    ForEachAdjacentUnit(unit->xPos, unit->yPos, TryAddMoveSkillTargetFem);
}}

static u8 MoveSkillUsabilityFem(int skill)
{{
    if (gActiveUnit->state & (US_HAS_MOVED | US_IN_BALLISTA | US_RESCUING) || !SkillTesterFem(gActiveUnit, skill))
        return MENU_NOTSHOWN;
    MakeMoveSkillTargetListFem(gActiveUnit, skill);
    return GetSelectTargetCount() ? MENU_ENABLED : MENU_NOTSHOWN;
}}

/* The units slide to their new tiles on the map (ticket 27, as C-SkillSys's HerosMovement: their map sprite walks one
   or two tiles), the player phase waiting; then the ally is set there, and the active unit "moves" there through the
   action before it waits */
struct MoveSkillAnimFem {{
    PROC_HEADER;
    struct Unit* unit[2];
    struct MuProc* mu[2];
    s8 x[2];
    s8 y[2];
    u8 tiles[2];
    u8 walked[2];
}};

static void MoveSkillAnimInitFem(struct MoveSkillAnimFem* proc)
{{
    int i;

    for (i = 0; i < 2 && proc->unit[i]; i++)
    {{
        struct Unit* unit = proc->unit[i];
        struct MuProc* mu = GetUnitMu(unit);

        if (!mu)
        {{
            HideUnitSprite(unit);
            mu = StartMu(unit);
        }}
        proc->mu[i] = mu;
        proc->walked[i] = 0;
        proc->tiles[i] = ABS(proc->x[i] - unit->xPos) + ABS(proc->y[i] - unit->yPos);
        if (mu)
        {{
            SetMuFacing(mu, GetFacingDirection(unit->xPos, unit->yPos, proc->x[i], proc->y[i]));
            if (unit != gActiveUnit)
                DisableMuCamera(mu);
        }}
    }}
}}

static void MoveSkillAnimLoopFem(struct MoveSkillAnimFem* proc)
{{
    int i, moving = FALSE;

    for (i = 0; i < 2 && proc->unit[i]; i++)
    {{
        if (!proc->mu[i] || proc->walked[i] >= proc->tiles[i])
            continue;
        Mu_OnStateMovement(proc->mu[i]);
        if (proc->mu[i]->move_clock_q4 == 0)
            proc->walked[i]++;
        moving = TRUE;
    }}
    if (!moving)
        Proc_Break(proc);
}}

static void MoveSkillAnimEndFem(struct MoveSkillAnimFem* proc)
{{
    int i;

    for (i = 0; i < 2 && proc->unit[i]; i++)
    {{
        if (proc->unit[i] == gActiveUnit)
            continue;   /* set by the action (gActionData.xMove), its map sprite ended there */
        if (proc->mu[i])
            EndMu(proc->mu[i]);
        proc->unit[i]->xPos = proc->x[i];
        proc->unit[i]->yPos = proc->y[i];
    }}
    RefreshEntityBmMaps();
    RefreshUnitSprites();
}}

static const struct ProcCmd sProcScr_MoveSkillAnimFem[] = {{
    PROC_YIELD,
    PROC_CALL(MoveSkillAnimInitFem),
    PROC_YIELD,
    PROC_REPEAT(MoveSkillAnimLoopFem),
    PROC_CALL(MoveSkillAnimEndFem),
    PROC_END,
}};

static u8 MoveSkillSelectFem(ProcPtr proc, struct SelectTarget* target)
{{
    struct Unit* unit = GetUnit(target->uid);
    struct Unit* mover;
    struct MoveSkillAnimFem* anim;
    ProcPtr phase = Proc_Find(gProcScr_PlayerPhase);
    int ux = gActiveUnit->xPos;
    int uy = gActiveUnit->yPos;
    int x, y;

    gActionData.xMove = ux;
    gActionData.yMove = uy;
    gActionData.unitActionType = UNIT_ACTION_WAIT;
    gSubjectUnit = gActiveUnit;
    if (MoveSkillDestinationFem(unit, ux, uy, &mover, &x, &y))
    {{
        anim = phase ? Proc_StartBlocking(sProcScr_MoveSkillAnimFem, phase)
                     : Proc_Start(sProcScr_MoveSkillAnimFem, PROC_TREE_3);
        anim->unit[0] = mover;
        anim->x[0] = x;
        anim->y[0] = y;
        anim->unit[1] = NULL;
        if (mover == gActiveUnit)
        {{
            gActionData.xMove = x;
            gActionData.yMove = y;
        }}
        else if (x == ux && y == uy)   /* Swap: the active unit to the ally's tile too */
        {{
            gActionData.xMove = unit->xPos;
            gActionData.yMove = unit->yPos;
            anim->unit[1] = gActiveUnit;
            anim->x[1] = unit->xPos;
            anim->y[1] = unit->yPos;
        }}
    }}
    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}}

static const struct SelectInfo sSelectInfoMoveSkillFem = {{
    .onEnd = MISMATCHED_SIGNATURE(ClearBg0Bg1),
    .onSelect = MoveSkillSelectFem,
    .onCancel = GenericSelection_BackToUM,
}};

static u8 MoveSkillEffectFem(int skill)
{{
    MakeMoveSkillTargetListFem(gActiveUnit, skill);
    NewTargetSelection(&sSelectInfoMoveSkillFem);
    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A;
}}
{rally}{commands}"""
    return out


# Batch 10, Outdoor Fighter: C-SkillSys's CheckOutdoorTerrain (KernelLib/Source/map.c), the terrains that are not indoors
OUTDOOR_TERRAINS = (
    "PLAINS", "ROAD", "VILLAGE_REGULAR", "VILLAGE_CLOSED", "HOUSE", "ARMORY", "VENDOR", "ARENA_REGULAR", "C_ROOM_09",
    "GATE_CASTLE", "FOREST", "THICKET", "SAND", "DESERT", "RIVER", "MOUNTAIN", "PEAK", "BRIDGE_REGULAR", "BRIDGE_14",
    "SEA", "LAKE", "GATE_REGULAR", "CHURCH", "RUINS_REGULAR", "CLIFF", "BALLISTA_REGULAR", "BALLISTA_LONG",
    "BALLISTA_KILLER", "SHIP_FLAT", "SHIP_WRECK", "TILE_2C", "ARENA_30", "VALLEY", "FENCE_32", "SNAG", "BRIDGE_SNAG", "SKY",
    "DEEPS", "RUINS_VILLAGE", "INN", "BARREL", "BONE", "DARK", "WATER", "DECK", "BRACE", "MAST")
_OUTDOOR = ("static int OutdoorTerrainFem(int terrain)\n{\n    switch (terrain) {\n"
            + "".join(f"    case TERRAIN_{t}:\n" for t in OUTDOOR_TERRAINS)
            + "        return TRUE;\n    default:\n        return FALSE;\n    }\n}\n\n")


def _aura_function(skills) -> str:
    """Batch 9, auras (C-SkillSys's PreBattleCalcAuraEffect): the units within 3 tiles of the unit in battle, from the
    map's unit layer; each holder's aura acts within its reach, then the unit's own skills counting the units around."""
    def lines(side, indent):
        pad = " " * indent
        return "".join(f"{pad}if (d <= {s.reach} && SkillTesterFem(unit, SKILL_FEM_{s.id}))\n{pad}    {s.code}\n"
                       for s in skills if s.kind == "aura" and s.side in (side, "both"))
    # batch 10, Blue Flame: the allies next to the unit that have it too
    flames = ("                flames1 += d == 1 && SkillTesterFem(unit, SKILL_FEM_BlueFlame);\n"
              if any(s.id == "BlueFlame" for s in skills) else "")
    own = "".join(f"    if (SkillTesterFem(&attacker->unit, SKILL_FEM_{s.id}))\n        {s.code}\n"
                  for s in skills if s.kind == "aura" and s.side == "self")
    return (
        "/* FE Maker: auras (C-SkillSys, PreBattleCalcAuraEffect) */\n"
        "s8 AreUnitsAllied(int left, int right);\n\n"
        "static void ApplyAuraSkillsFem(struct BattleUnit* attacker, struct BattleUnit* defender)\n{\n"
        "    int dx, dy, d, x, y;\n"
        "    int allies1 = 0, allies2 = 0, allies3 = 0, foes1 = 0, foes2 = 0, foes3 = 0, lords2 = 0, flames1 = 0;\n"
        "    struct Unit* unit;\n\n"
        "    if (gBattleStats.config & (BATTLE_CONFIG_ARENA | BATTLE_CONFIG_BIT2))\n        return;\n"
        "    for (dy = -3; dy <= 3; dy++) {\n"
        "        for (dx = -3; dx <= 3; dx++) {\n"
        "            d = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);\n"
        "            x = attacker->unit.xPos + dx;\n"
        "            y = attacker->unit.yPos + dy;\n"
        "            if (d == 0 || d > 3 || x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y"
        " || gBmMapUnit[y][x] == 0)\n                continue;\n"
        "            unit = GetUnit(gBmMapUnit[y][x]);\n"
        "            if (!UNIT_IS_VALID(unit) || unit->index == attacker->unit.index\n"
        "                || (unit->state & (US_HIDDEN | US_DEAD | US_RESCUED | US_BIT16)))\n"
        "                continue;\n"
        "            if (AreUnitsAllied(attacker->unit.index, unit->index)) {\n"
        "                allies3++;\n                allies2 += d <= 2;\n                allies1 += d == 1;\n"
        "                lords2 += d <= 2 && (UNIT_CATTRIBUTES(unit) & CA_LORD) != 0;\n"
        f"{flames}"
        f"{lines('ally', 16)}"
        "            } else {\n"
        "                foes3++;\n                foes2 += d <= 2;\n                foes1 += d == 1;\n"
        f"{lines('foe', 16)}"
        "            }\n        }\n    }\n"
        f"{own}"
        "    (void) defender; (void) allies1; (void) allies2; (void) allies3;"
        " (void) foes1; (void) foes2; (void) foes3; (void) lords2; (void) flames1;\n}\n\n")


def _ai_skills(decomp_dir: Path, files: dict, numbers: dict[str, int]) -> dict:
    """Batch 9, the enemy AI's choice of a target (C-SkillSys's AiOptimization.c and MiscAiSkills.c): Shade+ is never
    chosen, Shade is passed over at Luck %, Provoke adds 50 to the score of attacking its holder."""
    if not any(sid in numbers for sid in ("Shade", "ShadePlus", "Provoke")):
        return {}
    rel = "src/cp_battle.c"
    text = _read(files, decomp_dir, rel)
    skip = "".join((
        "            if (SkillTesterFem(unit, SKILL_FEM_ShadePlus)) /* FE Maker: Shade+ (C-SkillSys) */\n"
        "                continue;\n" if "ShadePlus" in numbers else "",
        "            if (SkillTesterFem(unit, SKILL_FEM_Shade) && Roll1RN(unit->lck)) /* FE Maker: Shade (C-SkillSys) */\n"
        "                continue;\n" if "Shade" in numbers else ""))
    if skip:
        text = _replace(text, """            if (unit->state & (US_HIDDEN | US_DEAD | US_RESCUED | US_BIT16))
                continue;

            if (!isEnemy(unit))
                continue;
""", f"""            if (unit->state & (US_HIDDEN | US_DEAD | US_RESCUED | US_BIT16))
                continue;

{skip}
            if (!isEnemy(unit))
                continue;
""", rel)
        text = _replace(text, '#include "cp_utility.h"\n', '#include "cp_utility.h"\n#include "rng.h"\n', rel)
    if "Provoke" in numbers:
        text = _replace(text, """    if (score > 40)
        score = 40;

    return score;
}
""", """    if (score > 40)
        score = 40;

    if (SkillTesterFem(&gBattleTarget.unit, SKILL_FEM_Provoke)) /* FE Maker: Provoke (C-SkillSys) */
        score += 50;

    return score;
}
""", rel)
    return {rel: text}


# batch 9: C-SkillSys's PrePhaseHeal.c, the % of max HP healed at the start of the phase (Imbue: its Magic)
HEAL_SKILLS = {
    "Renewal": "30",
    "Imbue": "",
    "Forager": "(terrain == TERRAIN_PLAINS || terrain == TERRAIN_FOREST || terrain == TERRAIN_MOUNTAIN) ? 20 : 0",
    "RainDish": "gPlaySt.chapterWeatherId == WEATHER_RAIN ? 30 : 0",
    "Relief": "allies == 0 ? 20 : 0",
    "Camaraderie": "allies != 0 ? 10 : 0",
}


def _growth_skills(decomp_dir: Path, files: dict, numbers: dict[str, int]) -> dict:
    """Batch 10, growths and experience, as C-SkillSys: Blossom doubles the growths (GrowthGetter.c) and halves the
    experience, Aptitude adds 20 to each growth, Paragon doubles the experience (BattleExp.c: of battles, staves and
    other actions, at most 100, at least 1 when there was some), Discipline doubles the weapon experience (BattleHit.c
    adds 2 a hit instead of 1; here, the weapon's experience twice, staves too). The growths are the ones the level-ups
    read (CheckBattleUnitLevelUp, UnitLevelUp), Magic's of strMagSplit included (strmag.apply runs before)."""
    growth = [sid for sid in ("Blossom", "Aptitude") if sid in numbers]
    exp = [sid for sid in ("Blossom", "Paragon") if sid in numbers]
    if not growth and not exp and "Discipline" not in numbers:
        return {}
    rel = "src/bmbattle.c"
    text = _read(files, decomp_dir, rel)
    if growth:
        def wrap(m):
            return f"GrowthFem({'&bu->unit' if m.group(1) == 'bu->unit.' else 'unit'}, {m.group(0)})"
        text = re.sub(r"(bu->unit\.|unit->)pCharacterData->growth\w+", wrap, text)
        text = re.sub(r"gCharacterMagFem\[(bu->unit\.|unit->)pCharacterData->number\]\[1\]", wrap, text)
        body = "".join({"Blossom": "    if (SkillTesterFem(unit, SKILL_FEM_Blossom))\n        result += growth;\n",
                        "Aptitude": "    if (SkillTesterFem(unit, SKILL_FEM_Aptitude))\n        result += 20;\n"}[sid]
                       for sid in growth)
        start = "void CheckBattleUnitLevelUp(struct BattleUnit* bu) {\n"
        text = _replace(text, start, f"""/* FE Maker: growth skills (C-SkillSys's GrowthGetter.c) */
static int GrowthFem(struct Unit* unit, int growth) {{
    int result = growth;

{body}    return result;
}}

""" + start, rel)
    if exp:
        body = "".join({"Blossom": "    if (SkillTesterFem(&bu->unit, SKILL_FEM_Blossom))\n        exp = exp / 2;\n",
                        "Paragon": "    if (SkillTesterFem(&bu->unit, SKILL_FEM_Paragon))\n        exp = exp * 2;\n"}[sid]
                       for sid in exp)
        start = "int GetBattleUnitExpGain(struct BattleUnit* actor, struct BattleUnit* target) {\n"
        text = _replace(text, start, f"""/* FE Maker: experience skills (C-SkillSys's KernelModifyBattleUnitExp) */
static int ExpFem(struct BattleUnit* bu, int exp) {{
    int base = exp;

{body}    if (exp > 100)
        exp = 100;
    if (base > 0 && exp <= 0)
        exp = 1;
    return exp;
}}

""" + start, rel)
        text = _replace(text, """    if (result < 1)
        result = 1;

    ModifyUnitSpecialExp(&actor->unit, &target->unit, &result);
""", """    if (result < 1)
        result = 1;

    result = ExpFem(actor, result);
    ModifyUnitSpecialExp(&actor->unit, &target->unit, &result);
""", rel)
        text = _replace(text, """    if (UNIT_CATTRIBUTES(&bu->unit) & CA_PROMOTED)
        result = result / 2;

    if (result > 100)
        result = 100;

    return result;
""", """    if (UNIT_CATTRIBUTES(&bu->unit) & CA_PROMOTED)
        result = result / 2;

    if (result > 100)
        result = 100;

    return ExpFem(bu, result);
""", rel)
        text = _replace(text, """    gBattleActor.expGain = 10;
    gBattleActor.unit.exp += 10;
""", """    gBattleActor.expGain = ExpFem(&gBattleActor, 10);
    gBattleActor.unit.exp += gBattleActor.expGain;
""", rel)
    if "Discipline" in numbers:
        text = _replace(text, "    result += GetItemAwardedExp(bu->weapon) * bu->wexpMultiplier;\n",
                        "    result += GetItemAwardedExp(bu->weapon) * bu->wexpMultiplier\n"
                        "        * (SkillTesterFem(&bu->unit, SKILL_FEM_Discipline) ? 2 : 1); /* FE Maker: Discipline */\n", rel)
    return {rel: text}


def _heal_function(heals) -> str:
    """The heal skills of `unit`, and Amaterasu (an ally's within 2 tiles), added up as C-SkillSys does; C-SkillSys
    looks at the first ally found only, for Amaterasu: here, any."""
    def line(sid):
        add = "GetUnitMagicFem(unit)" if sid == "Imbue" else f"GetUnitMaxHp(unit) * ({HEAL_SKILLS[sid]}) / 100"
        return f"    if (SkillTesterFem(unit, SKILL_FEM_{sid}))\n        ret += {add};\n"
    amaterasu = "Amaterasu" in heals
    return (
        "/* FE Maker: heal skills at the start of the phase (C-SkillSys, PrePhaseHeal.c) */\n"
        "static int PrePhaseHealFem(struct Unit* unit)\n{\n"
        "    int dx, dy, x, y, allies = 0, amaterasu = 0, ret = 0;\n"
        "    int terrain = gBmMapTerrain[unit->yPos][unit->xPos];\n"
        "    struct Unit* other;\n\n"
        "    for (dy = -2; dy <= 2; dy++) {\n"
        "        for (dx = -2; dx <= 2; dx++) {\n"
        "            x = unit->xPos + dx;\n            y = unit->yPos + dy;\n"
        "            if ((dx == 0 && dy == 0) || (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy) > 2 || x < 0 || y < 0\n"
        "                || x >= gBmMapSize.x || y >= gBmMapSize.y || gBmMapUnit[y][x] == 0)\n"
        "                continue;\n"
        "            other = GetUnit(gBmMapUnit[y][x]);\n"
        "            if (!UNIT_IS_VALID(other) || (other->state & (US_HIDDEN | US_DEAD | US_RESCUED | US_BIT16))\n"
        "                || !AreUnitsAllied(unit->index, other->index))\n"
        "                continue;\n"
        "            allies++;\n"
        + ("            if (SkillTesterFem(other, SKILL_FEM_Amaterasu))\n                amaterasu = 1;\n" if amaterasu else "")
        + "        }\n    }\n"
        + "".join(line(sid) for sid in heals if sid in HEAL_SKILLS)
        + ("    if (amaterasu)\n        ret += GetUnitMaxHp(unit) * 20 / 100;\n" if amaterasu else "")
        + "    (void) terrain; (void) allies; (void) amaterasu;\n    return ret;\n}\n\n")


POST_ACTION_SKILLS = ("Fury", "GrislyWound", "PoisonStrike", "Lifetaker", "Despoil", "BreathOfLife", "SavageBlow", "Lunge",
                      *(f"Seal{name}" for name, *_ in SEALS))


def uses_temp_bonuses(skills: list[Skill]) -> bool:
    """The seals need the temporary bonuses' counters (gamedata, before the skills are applied)."""
    return any(s.id.startswith("Seal") or s.id in RALLIES for s in skills)


def _post_action_skills(decomp_dir: Path, files: dict, numbers: dict[str, int], base: int) -> dict:
    """Batch 10, after the unit's action (C-SkillSys's PostActionHook, in the player phase and the AI's, before the
    game's traps): HP lost or healed after a battle, each unit in turn with the game's damage or heal animation on the
    map (C-SkillSys's MapAnims/Misc Hurt.c and Heal.c), and Despoil's Red Gem; first the seals, on the foe hit by the
    unit, with the temporary bonuses' counters, after C-SkillSys's animation (a flash on the unit, the first seal's
    icon beside the unit, MapAnimSkillMini.c, then Heavy Gravity's sprites falling on the foe, HeavyGravity.c)."""
    used = [sid for sid in POST_ACTION_SKILLS if sid in numbers]
    if not used:
        return {}
    seal_lines = "".join(
        f"    if (SkillTesterFem(gActiveUnit, SKILL_FEM_Seal{name}))\n"
        f"        bonuses = (bonuses & ~(15u << {4 * stat})) | (10u << {4 * stat});   /* -6 */\n"
        for name, _label, _short, stat in SEALS if f"Seal{name}" in used)
    first_seal = "".join(f"    if (SkillTesterFem(gActiveUnit, SKILL_FEM_Seal{name}))\n        return SKILL_FEM_Seal{name};\n"
                         for name, *_ in SEALS if f"Seal{name}" in used)
    def has(unit, sid):
        return f"SkillTesterFem({unit}, SKILL_FEM_{sid})" if sid in used else "FALSE"
    lunge_call = "    PROC_CALL(PostActionFem_Lunge),\n    PROC_YIELD,\n" if "Lunge" in used else ""
    code = f"""
/* FE Maker: skills after the action (C-SkillSys's PostActionHook and PostActionSkills), batch 10 */
void BeginUnitHealAnim(struct Unit* unit, int hp);   /* bmusailment.c */

struct PostActionFemProc {{
    PROC_HEADER;
    struct Unit* unit;
    int amount;    /* < 0: damage */
    u8 step;
    u8 next;       /* Breath of Life: the next unit index to look at */
    u8 lock;
    u8 defeated;   /* read once: the animations reset the battle's data */
    u8 seal;       /* the first seal of the actor, shown by the animation; 0: none */
    u8 timer;
    u8 tx, ty;     /* Savage Blow: where the foe stood */
    u8 damage;     /* Savage Blow: the actor's last damage */
}};

/* not US_HIDDEN: the active unit has it here, its map sprite still shown by its MU */
static int AliveOnMapFem(struct Unit* unit)
{{
    return unit && unit->pCharacterData && GetUnitCurrentHp(unit) > 0
        && !(unit->state & (US_DEAD | US_RESCUED | US_BIT16 | US_NOT_DEPLOYED));
}}

/* the actor hit its foe at least once (C-SkillSys's \"hitted\" flag), from the battle's hits */
static int ActorHitFem(void)
{{
    struct BattleHit* hit;

    for (hit = gBattleHitArray; !(hit->info & BATTLE_HIT_INFO_END); hit++)
        if (!(hit->info & BATTLE_HIT_INFO_RETALIATION) && !(hit->attributes & BATTLE_HIT_ATTR_MISS))
            return TRUE;
    return FALSE;
}}

/* Savage Blow: the damage of the actor's last hit (C-SkillSys takes the battle's last damage, maybe the foe's) */
static int ActorDamageFem(void)
{{
    struct BattleHit* hit;
    int damage = 0;

    for (hit = gBattleHitArray; !(hit->info & BATTLE_HIT_INFO_END); hit++)
        if (!(hit->info & BATTLE_HIT_INFO_RETALIATION) && !(hit->attributes & BATTLE_HIT_ATTR_MISS) && hit->hpChange > 0)
            damage = hit->hpChange;
    return damage;
}}

/* the first seal the actor has, when it hit a foe still on the map */
static int SealFem(void)
{{
    if (gActionData.unitActionType != UNIT_ACTION_COMBAT || !ActorHitFem() || !AliveOnMapFem(gActiveUnit)
        || !AliveOnMapFem(GetUnit(gActionData.targetIndex)))
        return 0;
{first_seal}    return 0;
}}

static int FifthFem(struct Unit* foe)
{{
    return GetUnitMaxHp(foe) / 5;
}}

/* the next unit and HP change to show; FALSE when none is left */
static int PostActionNextFem(struct PostActionFemProc* proc)
{{
    struct Unit* actor = gActiveUnit;
    struct Unit* target = gActionData.targetIndex ? GetUnit(gActionData.targetIndex) : NULL;
    int combat = gActionData.unitActionType == UNIT_ACTION_COMBAT && target;
    int defeated = combat && proc->defeated;
    int amount;

    while (TRUE) {{
        proc->unit = NULL;
        amount = 0;
        switch (proc->step++) {{
        case 0:   /* the actor's HP lost: Fury, the foe's Grisly Wound */
            if (combat && AliveOnMapFem(actor)) {{
                if ({has("actor", "Fury")})
                    amount += 6;
                if (target->pCharacterData && {has("target", "GrislyWound")})   /* a defeated foe is cleared */
                    amount += FifthFem(actor);
                proc->unit = actor;
            }}
            amount = -amount;
            break;
        case 1:   /* the target's: Poison Strike and Grisly Wound of the actor, its own Fury */
            if (combat && AliveOnMapFem(target)) {{
                if ({has("actor", "PoisonStrike")})
                    amount += FifthFem(target);
                if ({has("actor", "GrislyWound")})
                    amount += FifthFem(target);
                if ({has("target", "Fury")})
                    amount += 6;
                proc->unit = target;
            }}
            amount = -amount;
            break;
        case 2:   /* Lifetaker */
            if (defeated && AliveOnMapFem(actor) && {has("actor", "Lifetaker")}) {{
                amount = GetUnitMaxHp(actor) / 4;
                proc->unit = actor;
            }}
            break;
        case 3:   /* Despoil: a Red Gem, at Skill % (its text; C-SkillSys's code gives it every time) */
            if (defeated && AliveOnMapFem(actor) && {has("actor", "Despoil")} && Roll1RN(GetUnitSkill(actor))) {{
                NewPopup_ItemGot(proc, actor, ITEM_REDGEM);
                return TRUE;
            }}
            break;
        case 4:   /* Savage Blow: each foe within 2 tiles of the target loses 20 % of the actor's damage */
            if (combat && proc->damage >= 5 && AliveOnMapFem(actor) && {has("actor", "SavageBlow")}) {{
                while (proc->next < 0xC0 && !proc->unit) {{
                    struct Unit* unit = GetUnit(proc->next++);
                    int d;

                    if (!AliveOnMapFem(unit) || AreUnitsAllied(actor->index, unit->index))
                        continue;
                    d = (unit->xPos > proc->tx ? unit->xPos - proc->tx : proc->tx - unit->xPos)
                        + (unit->yPos > proc->ty ? unit->yPos - proc->ty : proc->ty - unit->yPos);
                    if (d <= 2) {{
                        proc->unit = unit;
                        amount = -(proc->damage / 5);
                    }}
                }}
                if (proc->unit) {{
                    proc->step--;
                    break;
                }}
            }}
            proc->next = 1;
            break;
        default:  /* Breath of Life: each ally within 2 tiles of the actor heals 20 % of its max HP */
            if (!combat || !AliveOnMapFem(actor) || !({has("actor", "BreathOfLife")}))
                return FALSE;
            while (proc->next < 0xC0) {{
                struct Unit* unit = GetUnit(proc->next++);
                int d;

                if (!AliveOnMapFem(unit) || unit == actor || !AreUnitsAllied(actor->index, unit->index))
                    continue;
                d = (unit->xPos > actor->xPos ? unit->xPos - actor->xPos : actor->xPos - unit->xPos)
                    + (unit->yPos > actor->yPos ? unit->yPos - actor->yPos : actor->yPos - unit->yPos);
                if (d > 2 || GetUnitCurrentHp(unit) == GetUnitMaxHp(unit))
                    continue;
                proc->unit = unit;
                amount = GetUnitMaxHp(unit) / 5;
                break;
            }}
            if (!proc->unit)
                return FALSE;
            proc->step--;
            break;
        }}
        if (!proc->unit)
            continue;
        if (amount < 0 && -amount >= GetUnitCurrentHp(proc->unit))   /* never kills */
            amount = 1 - GetUnitCurrentHp(proc->unit);
        if (amount > GetUnitMaxHp(proc->unit) - GetUnitCurrentHp(proc->unit))
            amount = GetUnitMaxHp(proc->unit) - GetUnitCurrentHp(proc->unit);
        if (amount != 0) {{
            proc->amount = amount;
            return TRUE;
        }}
    }}
}}

static void PostActionFem_Next(struct PostActionFemProc* proc)
{{
    if (!PostActionNextFem(proc))
        Proc_Goto(proc, 9);
    else if (!proc->unit)   /* a popup: back here once it is done */
        Proc_Goto(proc, 0);
}}

/* C-SkillSys's MapAnim_CommonInit and MapAnim_CommonEnd (KernelLib/Source/mapanim.c) */
static void PostActionFem_Init(struct PostActionFemProc* proc)
{{
    EndAllMus();
    RenderBmMap();
    RefreshEntityBmMaps();
    RefreshUnitSprites();
}}

static void PostActionFem_Camera(struct PostActionFemProc* proc)
{{
    EnsureCameraOntoPosition(proc, proc->unit->xPos, proc->unit->yPos);
}}

static void PostActionFem_Anim(struct PostActionFemProc* proc)
{{
    proc->lock = GetGameLock();
    HideUnitSprite(proc->unit);
    if (proc->amount < 0)
        BeginUnitCritDamageAnim(proc->unit, -proc->amount);
    else
        BeginUnitHealAnim(proc->unit, proc->amount);
}}

static void PostActionFem_Idle(struct PostActionFemProc* proc)
{{
    if (proc->lock == GetGameLock())
        Proc_Break(proc);
}}

static void PostActionFem_Apply(struct PostActionFemProc* proc)
{{
    AddUnitHp(proc->unit, proc->amount);
    ShowUnitSprite(proc->unit);
}}

static void PostActionFem_End(struct PostActionFemProc* proc)
{{
    InitBmBgLayers();
    LoadUiFrameGraphics();
    LoadObjUIGfx();
}}

/* Lunge (C-SkillSys's PostActionSwap, Swap.c): after a battle, the unit and its foe switch places, both alive and
   unpetrified, each able to stand on the other's tile; at once, without C-SkillSys's prompt to the player */
s8 CanUnitCrossTerrain(struct Unit* unit, int terrain);

static void PostActionFem_Lunge(struct PostActionFemProc* proc)
{{
    struct Unit* actor = gActiveUnit;
    struct Unit* target = gActionData.targetIndex ? GetUnit(gActionData.targetIndex) : NULL;
    int x, y;

    if (gActionData.unitActionType != UNIT_ACTION_COMBAT || !AliveOnMapFem(actor) || !AliveOnMapFem(target)
        || !{has("actor", "Lunge")} || actor->statusIndex == UNIT_STATUS_PETRIFY
        || actor->statusIndex == UNIT_STATUS_13 || target->statusIndex == UNIT_STATUS_PETRIFY
        || target->statusIndex == UNIT_STATUS_13
        || !CanUnitCrossTerrain(actor, gBmMapTerrain[target->yPos][target->xPos])
        || !CanUnitCrossTerrain(target, gBmMapTerrain[actor->yPos][actor->xPos]))
        return;
    EndAllMus();
    x = actor->xPos;
    y = actor->yPos;
    actor->xPos = target->xPos;
    actor->yPos = target->yPos;
    target->xPos = x;
    target->yPos = y;
    gActionData.xMove = actor->xPos;
    gActionData.yMove = actor->yPos;
    RefreshEntityBmMaps();
    RefreshUnitSprites();
}}

/* the seals' animation (C-SkillSys's MapAnimSkillMini.c and HeavyGravity.c, MIT): the unit's action animation, the
   flash on the unit (its image over the game's MISS one) and the seal's icon beside it, then sprites falling on the foe;
   only with a seal: its graphics and the temporary bonuses' counters are added for the seals alone */
#define SEALS_FEM {1 if first_seal else 0}
#if SEALS_FEM
extern const u8 gSkillAnimFem[];
extern const u8 gHeavyGravityFem[];

#define SEAL_ICON_CHR_FEM 0x19C
#define SEAL_ICON_PAL_FEM 4
#define SEAL_GRAVITY_CHR_FEM (0x53C0 / 0x20)

static void PostActionFem_SealStart(struct PostActionFemProc* proc)
{{
    if (!proc->seal) {{
        Proc_Goto(proc, 0);
        return;
    }}
    proc->unit = gActiveUnit;
}}

static void PostActionFem_SealWord(struct PostActionFemProc* proc)
{{
    struct Unit* unit = gActiveUnit;
    struct MuProc* mu = GetUnitMu(unit);

    if (!mu) {{
        HideUnitSprite(unit);
        mu = StartMu(unit);
    }}
    SetMuDefaultFacing(mu);
    SetDefaultColorEffects();
    StartMuActionAnim(mu);
    CpuFastCopy(gSkillAnimFem, OBJ_VRAM0 + 0x20 * BM_OBJCHR_BANIM_EFFECT, 12 * 0x20);
    APProc_Create(Obj_MapAnimMISS, 16 * SCREEN_TILE_X(unit->xPos) + 8, 16 * SCREEN_TILE_Y(unit->yPos) + 16,
                  TILEREF(BM_OBJCHR_BANIM_EFFECT, 0), 0, 2);
    PlaySeSpacial(0x3D1, SCREEN_TILE_IX(unit->xPos));
    LoadIconObjectGraphics({base} - 1 + proc->seal, SEAL_ICON_CHR_FEM);
    LoadIconPalette(0, 0x10 + SEAL_ICON_PAL_FEM);
    proc->timer = 0;
}}

static void PostActionFem_SealIcon(struct PostActionFemProc* proc)
{{
    struct Unit* unit = gActiveUnit;
    int x = unit->xPos == 0 ? 1 : unit->xPos - 1;

    PutSprite(4, OAM1_X(SCREEN_TILE_IX(x)), OAM0_Y(SCREEN_TILE_IY(unit->yPos)) + ATTR0_TYPE_BLENDED, gObject_16x16,
              OAM2_PAL(SEAL_ICON_PAL_FEM) + OAM2_LAYER(1) + OAM2_CHR(SEAL_ICON_CHR_FEM));
    if (++proc->timer == 40) {{
        proc->unit = GetUnit(gActionData.targetIndex);
        Proc_Break(proc);
    }}
}}

static void PostActionFem_GravityStart(struct PostActionFemProc* proc)
{{
    CpuFastCopy(gHeavyGravityFem, OBJ_VRAM0 + 0x53C0, 2 * 0x20);
    PlaySoundEffect(0x86);
    proc->timer = 0;
}}

/* three sprites, from the 10th, 20th and 30th frames, each falling for 16 frames */
static void PostActionFem_Gravity(struct PostActionFemProc* proc)
{{
    int ix = proc->unit->xPos * 16 - gBmSt.camera.x, iy = proc->unit->yPos * 16 - gBmSt.camera.y, k, t;

    proc->timer++;
    for (k = 10; k <= 30; k += 10) {{
        t = proc->timer - k;
        if (t >= 0 && t < 16)
            PutSprite(1, (ix + 0x200) & 0x1FF, (iy + t + 0xFD) & 0xFF, gObject_16x8,
                      OAM2_PAL(0) + OAM2_CHR(SEAL_GRAVITY_CHR_FEM) + OAM2_LAYER(1));
    }}
    if (proc->timer >= 30 + 16)
        Proc_Break(proc);
}}

static void PostActionFem_Seals(struct PostActionFemProc* proc)
{{
    struct Unit* target = GetUnit(gActionData.targetIndex);
    u32 bonuses = TEMP_BONUSES_FEM(target);

{seal_lines}    SET_TEMP_BONUSES_FEM(target, bonuses);
}}
#endif

struct ProcCmd CONST_DATA sProcScr_PostActionFem[] = {{
    PROC_NAME("FemPostAction"),
    PROC_YIELD,
#if SEALS_FEM
    PROC_CALL(PostActionFem_SealStart),
    PROC_YIELD,
    PROC_CALL(PostActionFem_Camera),
    PROC_YIELD,
    PROC_CALL(PostActionFem_SealWord),
    PROC_REPEAT(PostActionFem_SealIcon),
    PROC_CALL(PostActionFem_Camera),
    PROC_YIELD,
    PROC_CALL(PostActionFem_GravityStart),
    PROC_REPEAT(PostActionFem_Gravity),
    PROC_CALL(PostActionFem_Seals),
    PROC_CALL(PostActionFem_Init),
    PROC_YIELD,
    PROC_CALL(PostActionFem_End),
#endif
PROC_LABEL(0),
    PROC_CALL(PostActionFem_Next),
    PROC_YIELD,
    PROC_CALL(PostActionFem_Init),
    PROC_YIELD,
    PROC_CALL(PostActionFem_Camera),
    PROC_YIELD,
    PROC_CALL(PostActionFem_Anim),
    PROC_YIELD,
    PROC_REPEAT(PostActionFem_Idle),
    PROC_CALL(PostActionFem_Apply),
    PROC_YIELD,
    PROC_CALL(PostActionFem_End),
    PROC_GOTO(0),
PROC_LABEL(9),
{lunge_call}    PROC_END,
}};

void PostActionSkillsFem(ProcPtr parent)
{{
    struct PostActionFemProc* proc = Proc_StartBlocking(sProcScr_PostActionFem, parent);

    proc->step = 0;
    proc->next = 1;
    proc->defeated = gActionData.unitActionType == UNIT_ACTION_COMBAT && gBattleTarget.unit.curHP == 0;
    proc->seal = {"SealFem()" if first_seal else "0"};
    proc->tx = gBattleTarget.unit.xPos;
    proc->ty = gBattleTarget.unit.yPos;
    proc->damage = gActionData.unitActionType == UNIT_ACTION_COMBAT ? ActorDamageFem() : 0;
}}

"""
    out = {}
    rel = "src/playerphase.c"
    text = _read(files, decomp_dir, rel)
    text = _replace(text, '#include "playerphase.h"\n', '#include "playerphase.h"\n#include "popup.h"\n#include "rng.h"\n'
                    '#include "bmusailment.h"\n#include "uiutils.h"\n#include "ap.h"\n#include "ctc.h"\n'
                    '#include "icon.h"\n#include "bmlib.h"\n#include "mapanim.h"\n', rel)
    text = _replace(text, "struct ProcCmd CONST_DATA gProcScr_PlayerPhase[] =", code
                    + "struct ProcCmd CONST_DATA gProcScr_PlayerPhase[] =", rel)
    out[rel] = _replace(text, "    PROC_CALL_2(ApplyUnitAction),\n    PROC_CALL_2(HandlePostActionTraps),\n",
                        "    PROC_CALL_2(ApplyUnitAction),\n    PROC_CALL(PostActionSkillsFem), /* FE Maker */\n"
                        "    PROC_YIELD,\n    PROC_CALL_2(HandlePostActionTraps),\n", rel)
    rel = "src/cp_perform.c"
    text = _replace(_read(files, decomp_dir, rel), "struct ProcCmd CONST_DATA gProcScr_AiTargetCursor[] = {",
                    "void PostActionSkillsFem(ProcPtr parent);   /* FE Maker: playerphase.c */\n\n"
                    "struct ProcCmd CONST_DATA gProcScr_AiTargetCursor[] = {", rel)
    out[rel] = _replace(text, "    PROC_REPEAT(CpPerform_WaitAction),\n\n    PROC_CALL_2(HandlePostActionTraps),\n",
                        "    PROC_REPEAT(CpPerform_WaitAction),\n    PROC_CALL(PostActionSkillsFem), /* FE Maker */\n"
                        "    PROC_YIELD,\n\n    PROC_CALL_2(HandlePostActionTraps),\n", rel)
    if first_seal:
        rel = "data/data_item_icon.s"
        anim = "".join(f"\t.align 2\n\t.global {sym}\n{sym}:\n\t.incbin \"graphics/item_icon/{name}.4bpp\"\n"
                       for name, sym in (("skill_anim_fem", "gSkillAnimFem"), ("heavy_gravity_fem", "gHeavyGravityFem")))
        out[rel] = _replace(_read(files, decomp_dir, rel), "\t.global item_icon_palette\n",
                            anim + "\t.global item_icon_palette\n", rel)
        for name in SEAL_ANIM_URLS:
            out[f"graphics/item_icon/{name}.png"] = seal_anim_png(name)
    return out


GALEFORCE_USED = "0x02028E30"   # free RAM after the popups: 8 bytes, a bit per player unit, then the turn they are for


def _map_skills(decomp_dir: Path, files: dict, numbers: dict[str, int]) -> dict:
    """Batch 4, skills on the map, each patched in only when the project uses it: Canto+ (the game's Canto after a
    battle or a staff too), Renewal (with the terrain's heal at the start of the phase), Galeforce (the unit acts
    again after defeating an enemy, once a turn, every time: user's choice, C-SkillSys rolls Skill %)."""
    out = {}
    heals = [sid for sid in (*HEAL_SKILLS, "Amaterasu") if sid in numbers]
    if heals:
        rel = "src/bmtarget.c"
        text = _replace(_read(files, decomp_dir, rel), """\
        if (GetTerrainHealAmount(terrainId) != 0 && (GetUnitCurrentHp(unit) != GetUnitMaxHp(unit))) {
            amount = (GetTerrainHealAmount(terrainId) * GetUnitMaxHp(unit)) / 100;
            AddTarget(unit->xPos, unit->yPos, unit->index, amount);
        }
""", """        if (GetUnitCurrentHp(unit) != GetUnitMaxHp(unit)) { /* FE Maker: heal skills with the terrain (C-SkillSys) */
            amount = (GetTerrainHealAmount(terrainId) * GetUnitMaxHp(unit)) / 100 + PrePhaseHealFem(unit);
            if (amount != 0)
                AddTarget(unit->xPos, unit->yPos, unit->index, amount);
        }
""", rel)
        start = "void MakeTerrainHealTargetList(int faction) {\n"
        out[rel] = _replace(text, start, _heal_function(heals) + start, rel)
    if "CantoPlus" not in numbers and "Galeforce" not in numbers:
        return out
    rel = "src/playerphase.c"
    text = _read(files, decomp_dir, rel)
    if "CantoPlus" in numbers:
        text = _replace(text, """    if (!(UNIT_CATTRIBUTES(gActiveUnit) & CA_CANTO))
    {
        return false;
    }
""", """    if (!(UNIT_CATTRIBUTES(gActiveUnit) & CA_CANTO) && !SkillTesterFem(gActiveUnit, SKILL_FEM_CantoPlus))
    {
        return false;
    }
""", rel)
        text = _replace(text, """    switch (gActionData.unitActionType)
    {
        case UNIT_ACTION_WAIT:
        case UNIT_ACTION_COMBAT:
        case UNIT_ACTION_STAFF:
            return false;
    }
""", """    switch (gActionData.unitActionType)
    {
        case UNIT_ACTION_WAIT:
            return false;

        case UNIT_ACTION_COMBAT:
        case UNIT_ACTION_STAFF: /* FE Maker: Canto+ moves after them too */
            if (!SkillTesterFem(gActiveUnit, SKILL_FEM_CantoPlus))
                return false;
            break;
    }
""", rel)
    if "Galeforce" in numbers:
        text = _replace(text, '#include "bmunit.h"\n', '#include "bmunit.h"\n#include "rng.h"\n', rel)
        text = _replace(text, """    if (TryMakeCantoUnit(proc))
    {
        HideUnitSprite(gActiveUnit);
        return;
    }
""", """    if (!ShouldCallEndEvent() && TryGaleforceFem()) {   /* not when the chapter is won */
        RefreshUnitSprites();
        EndAllMus();
        StartStatusHealEffect(gActiveUnit, proc);   /* its flash and sound, as C-SkillSys */
    }
    else if (TryMakeCantoUnit(proc))
    {
        HideUnitSprite(gActiveUnit);
        return;
    }
""", rel)
        # ticket 23: a proc stops on its blocking child only when it yields; without this yield, the player phase
        # went on to its cursor and side windows (drawn on BG0, as the flash) during the flash, whose light column
        # then stayed on screen and the unit hidden
        text = _replace(text, "    PROC_CALL(PlayerPhase_FinishAction),\n\n    PROC_GOTO(0),\n",
                        "    PROC_CALL(PlayerPhase_FinishAction),\n    PROC_YIELD, /* FE Maker: Galeforce's flash */\n\n"
                        "    PROC_GOTO(0),\n", rel)
        text = _replace(text, "//! FE8U = 0x0801D344\nvoid PlayerPhase_FinishAction(ProcPtr proc)\n", f"""\
/* FE Maker: Galeforce (C-SkillSys's Tsuzuku.c): after a battle won, the unit acts again, once a turn (every time) */
#define sGaleforceUsedFem ((vu8*) {GALEFORCE_USED})
#define sGaleforceTurnFem (*(vu16*) ({GALEFORCE_USED} + 8))

void StartStatusHealEffect(struct Unit* unit, ProcPtr proc);   /* bmusailment.c */

static bool TryGaleforceFem(void)
{{
    int i = gActiveUnit->index;

    if (sGaleforceTurnFem != gPlaySt.chapterTurnNumber) {{
        for (i = 0; i < 8; i++)
            sGaleforceUsedFem[i] = 0;
        sGaleforceTurnFem = gPlaySt.chapterTurnNumber;
        i = gActiveUnit->index;
    }}
    if (gActionData.unitActionType != UNIT_ACTION_COMBAT || i >= 0x40 || (sGaleforceUsedFem[i / 8] & (1 << (i % 8)))
        || !SkillTesterFem(gActiveUnit, SKILL_FEM_Galeforce) || gActiveUnit->state & US_DEAD
        || gBattleTarget.unit.curHP != 0 || GetUnitCurrentHp(gActiveUnit) <= 0)
        return FALSE;
    sGaleforceUsedFem[i / 8] |= 1 << (i % 8);
    gActiveUnit->state &= ~(US_UNSELECTABLE | US_HAS_MOVED | US_HAS_MOVED_AI);
    return TRUE;
}}

//! FE8U = 0x0801D344
void PlayerPhase_FinishAction(ProcPtr proc)
""", rel)
    out[rel] = text
    if "Galeforce" in numbers:   # ticket 23: a chapter (re)started from its turn 1 forgets the turn's uses
        rel = "src/bmio.c"
        out[rel] = _replace(_read(files, decomp_dir, rel), "    gPlaySt.chapterTurnNumber = 0;\n", (
            "    gPlaySt.chapterTurnNumber = 0;\n"
            f"    *(vu16*) ({GALEFORCE_USED} + 8) = 0xFFFF; /* FE Maker: Galeforce's turn, none yet */\n"), rel)
    return out


# Skills that are not of the "order" kind but need the order code (an order part, or Double Lion's HP loss)
ORDER_EXTRA = frozenset({"Pursuer", "CloseCombat", "DoubleLion"})

# C-SkillSys's BattleUnwindConfig (Core/BattleSys/Source/data.c): the rounds for each mask (1 vantage, 2 desperation,
# 4 the actor doubles, 8 the target doubles); 1 the actor's round, 2 the target's
UNWIND_CONFIG = (
    (1, 2, 0, 0), (2, 1, 0, 0), (1, 2, 0, 0), (2, 1, 0, 0), (1, 2, 1, 0), (2, 1, 1, 0), (1, 1, 2, 0), (2, 1, 1, 0),
    (1, 2, 2, 0), (2, 1, 2, 0), (1, 2, 2, 0), (2, 1, 2, 0), (1, 2, 1, 2), (2, 1, 2, 1), (1, 1, 2, 2), (2, 1, 1, 2),
)


def _battle_order(battle: str, numbers: dict[str, int], rel: str) -> str:
    """The order of the rounds as C-SkillSys's BattleOrder.c (lot 7): Vantage and the like strike first, Desperation
    and the like follow up at once, skills that double or stop the foe from doubling, Last Word; the game's own
    follow-up rule otherwise."""
    def conds(*pairs):
        found = [f"({code})" for sid, code in pairs if sid in numbers]
        return " || ".join(found) if found else "FALSE"

    def has(unit, sid):
        return f"SkillTesterFem(&({unit})->unit, SKILL_FEM_{sid})"

    up = "->hpInitial * 2 > {0}->unit.maxHP"
    a_up, t_up = "a" + up.format("a"), "t" + up.format("t")
    despera = conds(
        ("Desperation", f"{has('a', 'Desperation')} && a->hpInitial * 2 < a->unit.maxHP"),
        ("CloseCombat", f"{has('a', 'CloseCombat')} && gBattleStats.range == 1"),
        ("Pursuer", has("a", "Pursuer")),
        ("YngviAscendant", has("a", "YngviAscendant")))
    vantage = conds(
        ("Vantage", f"{has('t', 'Vantage')} && t->hpInitial * 2 < t->unit.maxHP"),
        ("GaleWings", f"{has('t', 'GaleWings')} && t->hpInitial == t->unit.maxHP"),
        ("PridefulWarrior", has("a", "PridefulWarrior")))
    nullify = conds(
        ("WaryFighter", f"{has('t', 'WaryFighter')} && {t_up}"),
        ("Moonlight", has("a", "Moonlight")))
    if "YngviAscendant" in numbers:
        nullify = f"!{has('a', 'YngviAscendant')} && ({nullify})"
    reckless = ("RecklessFighter", f"({has('a', 'RecklessFighter')} && {a_up}) || ({has('t', 'RecklessFighter')}"
                                   f" && {t_up})")
    chaser = ("AdvantageChaser", f"{has('a', 'AdvantageChaser')} && (a->wTriangleDmgBonus > 0"
                                 " || a->wTriangleHitBonus > 0)")
    passion = ("PassionsFlow", f"{has('a', 'PassionsFlow')} && SupportedFem(a)")
    act = conds(
        ("BoldFighter", f"{has('a', 'BoldFighter')} && {a_up}"), reckless,
        ("BidingBlow", f"{has('a', 'BidingBlow')} && (!t->canCounter || !t->weapon)"), chaser,
        ("PridefulWarrior", has("a", "PridefulWarrior")), passion,
        ("BrashAssault", f"{has('a', 'BrashAssault')} && t->canCounter && t->weapon"))
    tar = conds(
        ("VengefulFighter", f"{has('a', 'VengefulFighter')} && {a_up}"), reckless,
        ("QuickRiposte", f"{has('a', 'QuickRiposte')} && {a_up}"), chaser, passion)
    last_word = (f"    if ({has('a', 'LastWord')} && CanFollowUpFem(a) && CanDoubleFem(t, a))\n        return TRUE;\n"
                 if "LastWord" in numbers else "")
    supported = """
static int SupportedFem(struct BattleUnit* bu)
{
    struct SupportBonuses bonuses;

    return bu->unit.index && GetUnit(bu->unit.index) && GetUnitSupportBonuses(GetUnit(bu->unit.index), &bonuses);
}
""" if "PassionsFlow" in numbers else ""
    lion = """
        /* Double Lion (C-SkillSys's PostActionSkills/Hurt.c): the actor loses 1 HP after its attack (no animation) */
        if (rounds[1] && gBattleActor.weaponBefore && (gBattleStats.config & BATTLE_CONFIG_REAL)
            && SkillTesterFem(&gBattleActor.unit, SKILL_FEM_DoubleLion)
            && gBattleActor.hpInitial == gBattleActor.unit.maxHP && gBattleActor.unit.curHP > 1)
            gBattleActor.unit.curHP--;
""" if "DoubleLion" in numbers else ""
    table = ",\n    ".join("{" + ", ".join(map(str, row)) + "}" for row in UNWIND_CONFIG)

    start = battle.index("void BattleUnwind(void) {")
    end = battle.index("void BattleGetBattleUnitOrder(", start)
    battle = battle[:start] + f"""/* FE Maker: order of the rounds (C-SkillSys's BattleOrder.c, BattleUnwindConfig) */
static const u8 sBattleUnwindFem[16][4] = {{
    {table}
}};
{supported}
static int CanFollowUpFem(struct BattleUnit* a)
{{
    if (gBattleTarget.battleSpeed > 250 || !a->weapon)
        return FALSE;
    if (GetItemWeaponEffect(a->weaponBefore) == WPN_EFFECT_HPHALVE)
        return FALSE;
    return GetItemIndex(a->weapon) != ITEM_MONSTER_STONE;
}}

/* C-SkillSys's CheckCanTwiceAttackOrder */
static int CanDoubleFem(struct BattleUnit* a, struct BattleUnit* t)
{{
    if (!CanFollowUpFem(a))
        return FALSE;
    if (a == &gBattleActor) {{
        if ({nullify})
            return FALSE;
        if ({act})
            return TRUE;
    }} else if ({tar})
        return TRUE;
    return a->battleSpeed - t->battleSpeed >= BATTLE_FOLLOWUP_SPEED_THRESHOLD;
}}

/* Whether the unit strikes twice (also the forecast's x2) */
int BattleDoublesFem(struct BattleUnit* a)
{{
    struct BattleUnit* t = a == &gBattleActor ? &gBattleTarget : &gBattleActor;

    if (CanDoubleFem(a, t))
        return TRUE;
{last_word}    return FALSE;
}}

void BattleUnwind(void) {{
    ClearBattleHits();

    do {{
        struct BattleUnit* a = &gBattleActor;
        struct BattleUnit* t = &gBattleTarget;
        const u8* config;
        int mask = 0, i, rounds[3] = {{0, 0, 0}};

        if (a->weapon && ({despera}))
            mask |= 2;
        if (t->weapon && ({vantage}))
            mask |= 1;
        if (BattleDoublesFem(a))
            mask |= 4;
        if (BattleDoublesFem(t))
            mask |= 8;
        config = sBattleUnwindFem[mask];

        gBattleHitIterator->info |= BATTLE_HIT_INFO_BEGIN;

        for (i = 0; i < 4 && config[i]; i++) {{
            if (config[i] == 1) {{
                if (rounds[1]++)
                    gBattleHitIterator->attributes = BATTLE_HIT_ATTR_FOLLOWUP;
                if (BattleGenerateRoundHits(a, t))
                    break;
            }} else {{
                if (rounds[2]++)
                    gBattleHitIterator->attributes = BATTLE_HIT_ATTR_FOLLOWUP;
                else
                    gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_RETALIATE;
                if (BattleGenerateRoundHits(t, a))
                    break;
            }}
        }}
{lion}    }} while (FALSE);

    gBattleHitIterator->info |= BATTLE_HIT_INFO_END;
}}

""" + battle[end:]
    start = battle.index("s8 BattleGetFollowUpOrder(")
    end = battle.index("s8 BattleGenerateRoundHits(", start)
    battle = battle[:start] + """s8 BattleGetFollowUpOrder(struct BattleUnit** outAttacker, struct BattleUnit** outDefender) {
    /* FE Maker: the order skills (C-SkillSys's BattleGetFollowUpOrder) */
    if (BattleDoublesFem(&gBattleActor)) {
        *outAttacker = &gBattleActor;
        *outDefender = &gBattleTarget;
        return TRUE;
    }
    if (BattleDoublesFem(&gBattleTarget)) {
        *outAttacker = &gBattleTarget;
        *outDefender = &gBattleActor;
        return TRUE;
    }
    return FALSE;
}

""" + battle[end:]
    if "Dazzle" in numbers or "Moonlight" in numbers:
        who = conds(("Dazzle", has("&gBattleActor", "Dazzle")), ("Moonlight", has("&gBattleActor", "Moonlight")))
        battle = _replace(battle, "    // Target cannot counter if a berserked player unit is attacking another player unit\n",
                          f"""    /* FE Maker: Dazzle and Moonlight (C-SkillSys's BattleWeapon.c) */
    if ({who}) {{
        gBattleTarget.weapon = 0;
        gBattleTarget.canCounter = FALSE;
    }}

    // Target cannot counter if a berserked player unit is attacking another player unit
""", rel)
    return battle


def _forecast_order(text: str, rel: str) -> str:
    """The forecast's x2 for each side (bksel.c), as both units may double with the order skills."""
    text = _replace(text, "void InitBattleForecastBattleStats(struct BattleForecastProc * proc)\n",
                    "int BattleDoublesFem(struct BattleUnit* unit); /* FE Maker: order skills (bmbattle.c) */\n\n"
                    "void InitBattleForecastBattleStats(struct BattleForecastProc * proc)\n", rel)
    for side in ("Actor", "Target"):
        text = _replace(text, f"        if ((followUp != 0) && (buFirst == &gBattle{side})) {{\n",
                        f"        if (BattleDoublesFem(&gBattle{side})) {{\n", rel)
    return text


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

/* "Eirika learned Luna.", blocking the proc */
void LearnedPopupFem(ProcPtr proc, struct Unit* unit, int skill)
{{
    const char* str;
    int i;

    if (skill <= 0 || skill > SKILL_COUNT_FEM)
        return;
    SetPopupUnit(unit);
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

/* PROC_REPEAT: one popup per learned skill (each blocks the proc), then on */
void LearnedPopupsFem(ProcPtr proc)
{{
    struct Unit* unit;
    int i, skill;

    if (sLearnedCountFem == 0 || sLearnedCountFem > 4) {{
        sLearnedCountFem = 0;
        Proc_Break(proc);
        return;
    }}
    skill = sLearnedQueueFem[1];
    unit = GetUnit(sLearnedQueueFem[0]);
    for (i = 1; i < sLearnedCountFem; i++) {{
        sLearnedQueueFem[2 * i - 2] = sLearnedQueueFem[2 * i];
        sLearnedQueueFem[2 * i - 1] = sLearnedQueueFem[2 * i + 1];
    }}
    sLearnedCountFem--;
    LearnedPopupFem(proc, unit, skill);
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
/* Batch 3: events give or take a skill: slot 1 the character, slot 2 the skill, slot 3 1 to give, 0 to take; a skill
   given shows the popup of a skill learned in battle (ticket 39), the event waiting for it (a STAL follows the call) */
#include "event.h"

void LearnedPopupFem(ProcPtr proc, struct Unit* unit, int skill);

void FemSkillEvent(ProcPtr proc)
{
    struct Unit* unit = GetUnitStructFromEventParameter(gEventSlots[1]);

    if (!unit)
        return;
    if (!gEventSlots[3])
        ForgetSkillFem(unit, gEventSlots[2]);
    else if (!SkillTesterFem(unit, gEventSlots[2])) {
        LearnSkillFem(unit, gEventSlots[2]);
        if (SkillTesterFem(unit, gEventSlots[2]))
            LearnedPopupFem(proc, unit, gEventSlots[2]);
    }
}
"""
    rel = "include/eventscript.h"
    out[rel] = _read(files, decomp_dir, rel).rstrip("\n") + (
        "\n\n/* FE Maker: skills for the events' GiveSkill / RemoveSkill */\n#define SKILLS_FEM_EVENTS 1\n"
        f'#include "{NUMBERS_HEADER.removeprefix("include/")}"\nvoid FemSkillEvent(void* proc);\n')
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
