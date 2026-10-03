/**
 * Marker art extracted from the retired map prototype.
 *
 * The prototype drew per-kind vector silhouettes straight onto its canvas; the
 * shapes and palette are preserved here so adoption did not lose them. Production
 * map markers render the archetypes that map cleanly onto the backend
 * place-group catalog via `markerArtDataUrl`; the rest fall back to the shared
 * Material icon. Every prototype drawer is kept, including the ones with no
 * catalog equivalent yet.
 */
export type IconDrawer = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string) => void

const ICON_OUTLINE = 'rgba(0, 0, 0, 0.85)'

/** Stroke a path twice: dark outline underneath, then the kind color on top. */
export function strokeWithOutline(
  ctx: CanvasRenderingContext2D,
  color: string,
  width: number,
  draw: () => void,
): void {
  ctx.lineWidth = width + 1.6
  ctx.strokeStyle = ICON_OUTLINE
  draw()
  ctx.lineWidth = width
  ctx.strokeStyle = color
  draw()
}

/** Vault door — gear ring; claimed vaults render as a filled gear. */
export function drawVaultDoor(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  color: string,
  claimed: boolean,
): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.4
  if (claimed) {
    ctx.beginPath()
    ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
    ctx.fill()
    for (let i = 0; i < 8; i++) {
      ctx.save()
      ctx.rotate((i * Math.PI) / 4)
      ctx.fillRect(4.5, -1.5, 2, 3)
      ctx.restore()
    }
    ctx.beginPath()
    ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = ICON_OUTLINE
    ctx.beginPath()
    ctx.arc(0, 0, 1.8, 0, Math.PI * 2)
    ctx.fill()
  } else {
    const ring = (): void => {
      ctx.beginPath()
      ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
      ctx.stroke()
      for (let i = 0; i < 8; i++) {
        ctx.save()
        ctx.rotate((i * Math.PI) / 4)
        ctx.beginPath()
        ctx.moveTo(2.2, 0)
        ctx.lineTo(4.8, 0)
        ctx.stroke()
        ctx.restore()
      }
      ctx.beginPath()
      ctx.arc(0, 0, 2.2, 0, Math.PI * 2)
      ctx.stroke()
    }
    strokeWithOutline(ctx, color, 1.4, ring)
  }
  ctx.restore()
}

/** Red Rocket — rocket silhouette with nose cone, fins and porthole. */
export function drawRocket(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(-2.2, 3.5)
  ctx.lineTo(-2.2, -3.5)
  ctx.quadraticCurveTo(-2.2, -6, 0, -6)
  ctx.quadraticCurveTo(2.2, -6, 2.2, -3.5)
  ctx.lineTo(2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-2.2, -3.5)
  ctx.lineTo(0, -8)
  ctx.lineTo(2.2, -3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-2.2, 1)
  ctx.lineTo(-5, 4.5)
  ctx.lineTo(-2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(2.2, 1)
  ctx.lineTo(5, 4.5)
  ctx.lineTo(2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(0, -1.5, 1.3, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

/** Super Duper Mart — storefront awning with scalloped edge and door. */
export function drawStore(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(-5.5, -5, 11, 4)
  ctx.strokeRect(-5.5, -5, 11, 4)
  for (let i = 0; i < 4; i++) {
    ctx.beginPath()
    ctx.arc(-4.125 + i * 2.75, -1, 1.375, 0, Math.PI)
    ctx.fill()
    ctx.stroke()
  }
  ctx.fillRect(-4.5, 0, 9, 3.5)
  ctx.strokeRect(-4.5, 0, 9, 3.5)
  ctx.fillStyle = ICON_OUTLINE
  ctx.fillRect(-1, 1.2, 2, 2.3)
  ctx.restore()
}

/** Radio Tower — lattice tower with signal arcs above the apex. */
export function drawTower(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  const lattice = (): void => {
    ctx.beginPath()
    ctx.moveTo(-3.2, 5)
    ctx.lineTo(0, -4)
    ctx.lineTo(3.2, 5)
    ctx.stroke()
    for (const y of [4, 2, 0, -2]) {
      const w = (3.2 * (5 - y)) / 9
      ctx.beginPath()
      ctx.moveTo(-w, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }
    for (const y of [4, 2, 0]) {
      const w1 = (3.2 * (5 - y)) / 9
      const w2 = (3.2 * (5 - (y - 2))) / 9
      ctx.beginPath()
      ctx.moveTo(-w1, y)
      ctx.lineTo(w2, y - 2)
      ctx.moveTo(w1, y)
      ctx.lineTo(-w2, y - 2)
      ctx.stroke()
    }
  }
  strokeWithOutline(ctx, color, 1.2, lattice)
  const arcs = (): void => {
    ctx.beginPath()
    ctx.arc(0, -4, 2.2, Math.PI * 0.15, Math.PI * 0.85, true)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(0, -4, 3.8, Math.PI * 0.25, Math.PI * 0.75, true)
    ctx.stroke()
  }
  strokeWithOutline(ctx, color, 1.2, arcs)
  ctx.restore()
}

/** Raider Camp — hostile skull mark. */
export function drawSkull(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.arc(0, -1.5, 5, Math.PI, 0)
  ctx.lineTo(5, 3)
  ctx.lineTo(-5, 3)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(-2, -1, 1.4, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(2, -1, 1.4, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.moveTo(-3, 1.5)
  ctx.lineTo(-3, 3)
  ctx.moveTo(0, 1.5)
  ctx.lineTo(0, 3)
  ctx.moveTo(3, 1.5)
  ctx.lineTo(3, 3)
  ctx.stroke()
  ctx.restore()
}

/** Abandoned Factory — sawtooth-roofed hall with chimney and smoke. */
export function drawFactory(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(2.5, -6, 2, 3)
  ctx.strokeRect(2.5, -6, 2, 3)
  ctx.beginPath()
  ctx.arc(3.5, -7.5, 1.2, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-5.5, 2.5)
  ctx.lineTo(-5.5, -2)
  ctx.lineTo(-2.75, -4.5)
  ctx.lineTo(0, -2)
  ctx.lineTo(2.75, -4.5)
  ctx.lineTo(5.5, -2)
  ctx.lineTo(5.5, 2.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.fillRect(-1, 0.5, 2, 2)
  ctx.restore()
}

/** Settlement — clustered houses with pitched roofs. */
export function drawHouses(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(-6, -1.5, 5, 4.5)
  ctx.strokeRect(-6, -1.5, 5, 4.5)
  ctx.beginPath()
  ctx.moveTo(-6.5, -1.5)
  ctx.lineTo(-3.5, -5)
  ctx.lineTo(-0.5, -1.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(1, -0.5, 5, 3.5)
  ctx.strokeRect(1, -0.5, 5, 3.5)
  ctx.beginPath()
  ctx.moveTo(0.5, -0.5)
  ctx.lineTo(3.5, -4)
  ctx.lineTo(6.5, -0.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(-5, -3.5, 1.5, 2)
  ctx.strokeRect(-5, -3.5, 1.5, 2)
  ctx.restore()
}

/** Water Treatment — water drop with highlight. */
export function drawWaterDrop(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(0, -6.5)
  ctx.bezierCurveTo(3.8, -2.5, 4.5, -0.5, 4.5, 1.5)
  ctx.arc(0, 1.5, 4.5, 0, Math.PI)
  ctx.bezierCurveTo(-4.5, -0.5, -3.8, -2.5, 0, -6.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(-1.4, 0.8, 1.1, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

/** Supply Cache — small rounded crate with a lid band and diagonal brace. */
export function drawSupplyCrate(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  const r = 1.5
  ctx.beginPath()
  ctx.moveTo(-5 + r, -3.5)
  ctx.lineTo(5 - r, -3.5)
  ctx.quadraticCurveTo(5, -3.5, 5, -3.5 + r)
  ctx.lineTo(5, 4 - r)
  ctx.quadraticCurveTo(5, 4, 5 - r, 4)
  ctx.lineTo(-5 + r, 4)
  ctx.quadraticCurveTo(-5, 4, -5, 4 - r)
  ctx.lineTo(-5, -3.5 + r)
  ctx.quadraticCurveTo(-5, -3.5, -5 + r, -3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(-5, -3.5, 10, 1.8)
  ctx.strokeRect(-5, -3.5, 10, 1.8)
  ctx.beginPath()
  ctx.moveTo(-4, 3.5)
  ctx.lineTo(4, -1.5)
  ctx.stroke()
  ctx.restore()
}

/** Generic diamond fallback for prototype kinds not yet mapped to an archetype. */
export function drawUnknown(ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(0, -5.5)
  ctx.lineTo(4.5, 0)
  ctx.lineTo(0, 5.5)
  ctx.lineTo(-4.5, 0)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.restore()
}

interface MarkerArt {
  draw: IconDrawer
  color: string
}

/**
 * Prototype kind table, preserved verbatim. `red_rocket`, `super_duper_mart`
 * and `abandoned_factory` are the prototype's names for catalog archetypes the
 * production map now adopts (see `ARCHETYPE_ART`).
 */
export const PROTOTYPE_KIND_ART: Record<string, MarkerArt> = {
  settlement: { color: '#00ff00', draw: drawHouses },
  red_rocket: { color: '#ff6b6b', draw: drawRocket },
  super_duper_mart: { color: '#ffd43b', draw: drawStore },
  abandoned_factory: { color: '#c8b9ae', draw: drawFactory },
  radio_tower: { color: '#00d9ff', draw: drawTower },
  water_treatment: { color: '#4dabf7', draw: drawWaterDrop },
  raider_camp: { color: '#ff7043', draw: drawSkull },
  supply_cache: { color: '#d4a24e', draw: drawSupplyCrate },
}

/** Catalog group_key → prototype art, for the archetypes that map cleanly. */
export const ARCHETYPE_ART: Record<string, MarkerArt> = {
  settlement: PROTOTYPE_KIND_ART.settlement,
  gas_station: PROTOTYPE_KIND_ART.red_rocket,
  supermarket: PROTOTYPE_KIND_ART.super_duper_mart,
  factory: PROTOTYPE_KIND_ART.abandoned_factory,
}

// Drawers span roughly ±8 units plus stroke; render into a 32px tile with a
// little padding so nothing clips.
const TILE_SIZE = 32
const DRAW_SPAN = 24

const urlCache = new Map<string, string>()

/**
 * Rendered data URL for a location's archetype art, or null when the archetype
 * has no preserved silhouette (caller falls back to the Material icon).
 */
export function markerArtDataUrl(groupKey: string | null | undefined): string | null {
  if (!groupKey) return null
  const art = ARCHETYPE_ART[groupKey]
  if (!art) return null
  const cached = urlCache.get(groupKey)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = TILE_SIZE
  canvas.height = TILE_SIZE
  const ctx = canvas.getContext('2d')
  if (ctx === null) return null
  ctx.translate(TILE_SIZE / 2, TILE_SIZE / 2)
  ctx.scale(TILE_SIZE / DRAW_SPAN, TILE_SIZE / DRAW_SPAN)
  art.draw(ctx, 0, 0, art.color)
  const url = canvas.toDataURL()
  urlCache.set(groupKey, url)
  return url
}
