// PoC scene descriptor for the layered-actor arena stage (issues 818 and 819).
// Placeholder geometry only — proves anchors + layering + equipment swap +
// fallback + reduced-motion before any art generation or manifest convention
// exists. Anchors are authored in the scene's intrinsic pixel space and
// converted to percentages so the stage stays resolution-independent.
// TODO(819): replace with the agreed scene manifest
export interface SceneAnchorSpec {
  id: string
  /** Anchor x in the scene's intrinsic pixel space, from the left edge. */
  x: number
  /** Anchor y (feet line) in intrinsic pixels; defaults to floorBaseline for depth variation. */
  y?: number
}

export interface ActorLayerPlacement {
  widthPercent: number
  rightPercent: number
  bottomPercent: number
}

export interface ArenaSceneDescriptor {
  intrinsicWidth: number
  intrinsicHeight: number
  /** Intrinsic-pixel y of the floor line actors stand on. */
  floorBaseline: number
  /** Actor width as a percentage of the stage width; height derives from aspect-ratio. */
  actorWidthPercent: number
  /** Weapon layer placement within the actor box (per-layer anchor; full-bleed when omitted). */
  weaponLayer: ActorLayerPlacement
  anchors: SceneAnchorSpec[]
}

export const ARENA_SCENE_POC: ArenaSceneDescriptor = {
  intrinsicWidth: 1536,
  intrinsicHeight: 1024,
  floorBaseline: 717,
  actorWidthPercent: 16,
  weaponLayer: { widthPercent: 60, rightPercent: 0, bottomPercent: 28 },
  anchors: [
    { id: 'slot-1', x: 492, y: 737 },
    { id: 'slot-2', x: 1106, y: 717 },
  ],
}

export interface AnchorPercent {
  left: string
  top: string
}

/** Converts an anchor from intrinsic pixel space to stage percentages. */
export function anchorToPercent(
  anchor: SceneAnchorSpec,
  scene: ArenaSceneDescriptor = ARENA_SCENE_POC
): AnchorPercent {
  const baseline = anchor.y ?? scene.floorBaseline
  return {
    left: `${(anchor.x / scene.intrinsicWidth) * 100}%`,
    top: `${(baseline / scene.intrinsicHeight) * 100}%`,
  }
}
