import type { MapsData, TilesetEdits } from './types'

/** 8x8 tile number of a tile config entry (bits 10-15: flips and palette). */
const TILE_NUMBER = 0x3ff

/** The edits without the 8x8 tiles no added metatile uses any more (the game's metatiles never
 *  use them: they were free tiles of the tileset image, server tileedit.py). */
export function withoutOrphanTiles(edits: TilesetEdits): TilesetEdits {
  const used = new Set(Object.values(edits.metatiles).flatMap((m) => m.tiles.map((e) => e & TILE_NUMBER)))
  return { metatiles: edits.metatiles, tiles: Object.fromEntries(Object.entries(edits.tiles).filter(([k]) => used.has(Number(k)))) }
}

/** The edits without these added metatiles (and their own 8x8 tiles). */
export function withoutMetatiles(edits: TilesetEdits, slots: string[]): TilesetEdits {
  const metatiles = Object.fromEntries(Object.entries(edits.metatiles).filter(([k]) => !slots.includes(k)))
  return withoutOrphanTiles({ metatiles, tiles: edits.tiles })
}

/** Proposed edits (a mirror or turn, ticket 22) keeping, of the metatiles not saved yet, only those
 *  the block uses (a turn of a turn leaves the first one unused). */
export function keepUsed(edits: TilesetEdits, saved: TilesetEdits | undefined, rows: number[][]): TilesetEdits {
  const used = new Set(rows.flat().map(String))
  const drop = Object.keys(edits.metatiles).filter((k) => !(saved && k in saved.metatiles) && !used.has(k))
  return withoutMetatiles(edits, drop)
}

/** Cells of the project's maps and map changes drawn with each added metatile of a tileset.
 *  `tilesetOf`: the tile config a layout is drawn with (its own, or the sheet chosen for it). */
export function addedTileUsage(data: MapsData | undefined, edits: TilesetEdits, tileset: string,
                               layouts: string[], tilesetOf: (layout: string) => string): Map<string, { cells: number; maps: string[] }> {
  const out = new Map<string, { cells: number; maps: string[] }>()
  for (const id of layouts) {
    if (tilesetOf(id) !== tileset) continue
    const grids = [data?.layouts?.[id]?.rows ?? [], ...(data?.changes?.[id] ?? []).map((c) => c.rows)]
    for (const grid of grids) {
      for (const m of grid.flat()) {
        const key = String(m)
        if (!(key in edits.metatiles)) continue
        const u = out.get(key) ?? { cells: 0, maps: [] }
        u.cells++
        if (!u.maps.includes(id)) u.maps.push(id)
        out.set(key, u)
      }
    }
  }
  return out
}
