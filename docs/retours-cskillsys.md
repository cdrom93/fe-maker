# Retours au C-SkillSys (brouillon)

Écarts trouvés en adaptant le C-SkillSys (https://github.com/MokhaLeee/fe8u-cskillsys-kernel), commit suivi
`fb545870` (encore le dernier de `main` au 07/11/2026). **Rien n'est envoyé** : choix de l'utilisateur (07/11/2026),
on garde ce brouillon jusqu'à la fin de l'adaptation, on le complète à chaque lot, puis on ouvre un seul ticket
(issue) et, pour les corrections évidentes, une proposition de correctif (pull request) chacune, sur son accord.

Pour chaque écart : ce que fait FE Maker (`docs/competences.md`), et si un correctif simple est possible.

| Compétence | FE Maker suit | Correctif proposable |
|---|---|---|
| Puissance | la description | oui : comparer `battleAttack` (une condition) |
| Reckless Fighter | la description | à demander : intention pas claire |
| Last Word | la description | oui : tester que l'adversaire double (`round_mask`) |
| Armsthrift | le code (Chance) | oui : le texte (« Luck % ») ou le code |
| Vengeance | la description | à demander : pas d'effet du tout |

Correctifs : on ne peut pas compiler leur noyau ici (leur chaîne de compilation), donc chaque correctif reste petit,
lisible et marqué « non testé dans leur build ».

## Brouillon du ticket (en anglais)

**Title:** Skill descriptions that don't match their code (Puissance, Reckless Fighter, Last Word, Armsthrift, Vengeance)

While reading the skill code at fb545870 (current `main`), I found a few skills whose effect differs from their
description. Listed here in case they are not intended:

- **Puissance** (`Kernel/Wizardry/Core/BattleSys/Source/BattleCalcReal.c`): the text says "+3 Attack if the unit's
  attack is greater than the enemy's", but the bonus sits in the `attacker->battleSpeed > defender->battleSpeed`
  block, so it compares speed.
- **Reckless Fighter** (`BattleOrder.c`, `CheckCanTwiceAttackOrder`): the text says "If HP is higher than 50%, both
  sides always attack twice". As the actor, the holder's HP is checked (`ref_actor_hp_above_half`, or
  `hpInitial * 2 >= maxHP` for a target holder); as the target, neither unit's HP is checked.
- **Last Word** (`BattleOrder.c`, `PostCalc_ModifyBattleOrderRoundMask`): the text says "If the enemy doubles, this
  unit doubles", but the unit gets `UNWIND_DOUBLE_ACT` / `UNWIND_DOUBLE_TAR` whenever it doesn't double already,
  without looking at the enemy's flag.
- **Armsthrift** (`BattleHitAttr.c`, `BattleHit_ConsumeWeapon`): the text says "(Skill % activation)", the code
  rolls `attacker->unit.lck`.
- **Vengeance**: it has a text ("Add damage taken to attack. (Skill % activation)"), an icon and an animation entry,
  but no effect in the battle code.

<!-- Ajouter ici les écarts des lots suivants, au même format. -->
