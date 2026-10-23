/** Unit AI: 4 bytes (src/cp_data.c) — action, movement, target/recovery settings, flags. */

export const AI_ACTION_COUNT = 0x15 // gAi1ScriptTable
export const AI_MOVE_COUNT = 0x13 // gAi2ScriptTable
export const AI_TARGET_COUNT = 32 // gAiCombatScoreCoefficientTable
export const AI_NAMED_TARGETS = 6
export const AI_RECOVERY_COUNT = 5 // gAI3HealingThresholdTable
export const AI_GUARD_TILE = 0x20

/** Common action + movement pairs, as used in the original game (label: ai.preset.<key>). */
export const AI_PRESETS: [string, number, number][] = [
  ['chase', 0x00, 0x00],
  ['inRange', 0x00, 0x03],
  ['standGround', 0x03, 0x03],
  ['approach', 0x00, 0x06],
  ['afterTurn', 0x00, 0x12],
  ['healer', 0x0e, 0x03],
  ['brigand', 0x00, 0x04],
  ['looter', 0x06, 0x05],
  ['thief', 0x10, 0x05],
  ['walls', 0x00, 0x0e],
  ['nothing', 0x06, 0x03],
]

/** Preset key matching the AI bytes, or 'custom'. */
export function aiPreset(ai: number[] | string): string {
  if (!Array.isArray(ai)) return 'custom'
  return AI_PRESETS.find(([, a, m]) => a === ai[0] && m === ai[1])?.[0] ?? 'custom'
}
