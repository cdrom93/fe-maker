// Version of the portraits shown in the app: bumped when the project imports or removes a portrait,
// so that every <img> of a portrait loads it again (server: decomp/portraits.py).
export const portraitVersion = $state({ n: 0 })

export function portraitsChanged() {
  portraitVersion.n++
}

// Same for the map sprites a project imports for its classes (server: decomp/mapsprites.py).
export const mapSpriteVersion = $state({ n: 0 })

/** Bumped when the project imports or removes an item icon. */
export const iconVersion = $state({ n: 0 })
