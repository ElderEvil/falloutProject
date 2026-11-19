/** Development-only forward-kinematic rig. Coordinates are local to each parent joint. */
export type BoneId =
  | 'pelvis'
  | 'spine'
  | 'head'
  | 'backUpperArm'
  | 'backForearm'
  | 'backHand'
  | 'frontUpperArm'
  | 'frontForearm'
  | 'frontHand'
  | 'backThigh'
  | 'backShin'
  | 'backFoot'
  | 'frontThigh'
  | 'frontShin'
  | 'frontFoot'
export type RigClip = 'bind' | 'idle' | 'walk' | 'punch'
export type JointAngles = Partial<Record<BoneId, number>>
type Point = readonly [number, number]
type Rect = readonly [number, number, number, number]
interface Bone {
  id: BoneId
  label: string
  parent: BoneId | null
  offset: Point
  end: Point
  layer: number
  bindAngle: number
  sprite: {
    sheet: 'suit' | 'head' | 'hands'
    crop: Rect
    frame: Rect
    flipY?: boolean
    flipX?: boolean
    rotation?: number
  }
}
export type RigSprite = Bone['sprite']
export type SpriteOverrides = Partial<Record<BoneId, RigSprite>>

export interface RigJoint extends Bone {
  x: number
  y: number
  angle: number
  tip: Point
}

// Artwork placement is independent of the joint axis: fit visible outline anchors in the
// reference, retaining uniform limb scale. Shoe heel/toe anchors are documented beside the assets.
const bodyParts: readonly Omit<Bone, 'offset' | 'end' | 'bindAngle'>[] = [
  {
    id: 'pelvis',
    label: 'Waist / pelvis',
    parent: null,
    layer: 1.5,
    sprite: {
      sheet: 'suit',
      crop: [397, 109, 83, 82],
      frame: [-61.239, -50.4335, 103, 101.759],
      rotation: -20,
    },
  },
  {
    id: 'spine',
    label: 'Spine',
    parent: 'pelvis',
    layer: 4,
    sprite: {
      sheet: 'suit',
      crop: [157, 18, 86, 104],
      frame: [-69.8495, -97.1017, 113.95, 113.8325],
      rotation: 3.9839,
      flipX: true,
    },
  },
  {
    id: 'head',
    label: 'Head',
    parent: 'spine',
    layer: 8,
    sprite: { sheet: 'head', crop: [0, 0, 94, 96], frame: [-68.75, -108.75, 117.5, 120] },
  },
  {
    id: 'backUpperArm',
    label: 'Back shoulder · left arm',
    parent: 'spine',
    layer: 1,
    sprite: {
      sheet: 'suit',
      crop: [283, 28, 31, 73],
      frame: [-12.2524, -6.8787, 27.7731, 65.4012],
      rotation: 4.6155,
    },
  },
  {
    id: 'backForearm',
    label: 'Back elbow · left arm',
    parent: 'backUpperArm',
    layer: 1,
    sprite: {
      sheet: 'suit',
      crop: [334, 110, 36, 72],
      frame: [-12.4997, -9.1513, 24.2879, 48.5758],
      rotation: 13.5726,
    },
  },
  {
    id: 'backHand',
    label: 'Back wrist · left arm',
    parent: 'backForearm',
    layer: 1,
    sprite: {
      sheet: 'hands',
      crop: [19, 62, 57, 44],
      frame: [-3.75, -9.375, 35.625, 27.5],
      rotation: 75.4353,
    },
  },
  {
    id: 'frontUpperArm',
    label: 'Front shoulder · right arm',
    parent: 'spine',
    layer: 7,
    sprite: {
      sheet: 'suit',
      crop: [330, 13, 36, 90],
      frame: [-9.1196, -26.4343, 33.1052, 82.7629],
      rotation: 3.6325,
      flipY: true,
    },
  },
  {
    id: 'frontForearm',
    label: 'Front elbow · right arm',
    parent: 'frontUpperArm',
    layer: 7,
    sprite: {
      sheet: 'suit',
      crop: [279, 110, 31, 70],
      frame: [-12.5008, -10.7498, 31.0012, 70.0026],
      rotation: -1.3331,
    },
  },
  {
    id: 'frontHand',
    label: 'Front wrist · right arm',
    parent: 'frontForearm',
    layer: 7,
    sprite: {
      sheet: 'hands',
      crop: [19, 62, 57, 44],
      frame: [-40.7661, -11.9901, 45.5622, 35.1707],
      flipX: true,
      rotation: -104.2039,
    },
  },
  {
    id: 'backThigh',
    label: 'Back hip · left leg',
    parent: 'pelvis',
    layer: 0,
    sprite: {
      sheet: 'suit',
      crop: [19, 19, 49, 101],
      frame: [-29.2129, -4.608, 38.1651, 78.6668],
      rotation: -7.08,
    },
  },
  {
    id: 'backShin',
    label: 'Back knee · left leg',
    parent: 'backThigh',
    layer: -0.1,
    sprite: {
      sheet: 'suit',
      crop: [22, 132, 41, 78],
      frame: [-9.217, 3.7639, 28.0493, 53.3621],
      rotation: 9.6518,
    },
  },
  {
    id: 'backFoot',
    label: 'Back ankle · left leg',
    parent: 'backShin',
    layer: 0,
    sprite: {
      sheet: 'suit',
      crop: [378, 213, 53, 33],
      frame: [-10.0711, -6.1738, 45.8069, 28.5213],
      flipX: true,
      rotation: -15.1474,
    },
  },
  {
    id: 'frontThigh',
    label: 'Front hip · right leg',
    parent: 'pelvis',
    layer: 2,
    sprite: {
      sheet: 'suit',
      crop: [80, 18, 48, 98],
      frame: [-35.2639, -11.8039, 49.88, 101.8384],
      rotation: 0.3681,
    },
  },
  {
    id: 'frontShin',
    label: 'Front knee · right leg',
    parent: 'frontThigh',
    layer: 1.75,
    sprite: {
      sheet: 'suit',
      crop: [85, 135, 42, 79],
      frame: [-30.1223, 5.7827, 32.4242, 60.9885],
      rotation: -14.0256,
    },
  },
  {
    id: 'frontFoot',
    label: 'Front ankle · right leg',
    parent: 'frontShin',
    layer: 2,
    sprite: {
      sheet: 'suit',
      crop: [447, 213, 62, 34],
      frame: [-33.9834, -12.1689, 70.5415, 38.684],
      flipX: true,
      rotation: -15.2252,
    },
  },
]

export const RIG_REFERENCE = { x: 107.5, y: 90.25, scale: 1.25, width: 136, height: 287 }

// Joint locations in the unmodified Chet reference. The separated atlas parts remain the skin.
// Both hips pivot near the pelvis centre (not on Chet's silhouette) so thighs swing from one hip.
// Three-quarter view: the far (left) shoulder sits inside the torso outline, hidden behind it.
const landmarks: Record<BoneId, { point: Point; tip: Point }> = {
  pelvis: { point: [74, 164], tip: [74, 152] },
  spine: { point: [74, 160], tip: [74, 87] },
  head: { point: [74, 87], tip: [74, 10] },
  backUpperArm: { point: [93, 103], tip: [113, 150] },
  backForearm: { point: [113, 150], tip: [120, 179] },
  backHand: { point: [120, 179], tip: [125, 204] },
  frontUpperArm: { point: [41, 106], tip: [21, 143] },
  frontForearm: { point: [21, 143], tip: [20, 186] },
  frontHand: { point: [20, 186], tip: [23, 206] },
  backThigh: { point: [66, 175], tip: [43, 218] },
  backShin: { point: [43, 218], tip: [30, 254] },
  backFoot: { point: [30, 254], tip: [40, 279] },
  frontThigh: { point: [60, 175], tip: [81, 224] },
  frontShin: { point: [81, 224], tip: [79, 268] },
  frontFoot: { point: [79, 268], tip: [109, 277] },
}
function bindHeading(id: BoneId): number {
  if (id === 'backFoot') return 55
  if (id === 'frontHand') return -19
  if (id === 'backHand') return -23
  if (
    !id.endsWith('UpperArm') &&
    !id.endsWith('Forearm') &&
    !id.endsWith('Thigh') &&
    !id.endsWith('Shin')
  )
    return 0
  const { point, tip } = landmarks[id]
  return (Math.atan2(point[0] - tip[0], tip[1] - point[1]) * 180) / Math.PI
}
export const RIG_BONES: readonly Bone[] = bodyParts.map((bone) => {
  const { point, tip } = landmarks[bone.id]
  const parent = bone.parent ? landmarks[bone.parent] : undefined
  const angle = bindHeading(bone.id)
  const parentAngle = bone.parent ? bindHeading(bone.parent) : 0
  const { scale, x, y } = RIG_REFERENCE
  return {
    ...bone,
    bindAngle: angle - parentAngle,
    offset: parent
      ? rotate(
          [(point[0] - parent.point[0]) * scale, (point[1] - parent.point[1]) * scale],
          -parentAngle
        )
      : [x + point[0] * scale, y + point[1] * scale],
    end: rotate([(tip[0] - point[0]) * scale, (tip[1] - point[1]) * scale], -angle),
  }
})

export const RIG_CLIPS: Record<RigClip, { label: string; duration: number; description: string }> =
  {
    bind: {
      label: 'Bind pose',
      duration: 1,
      description: 'Chet’s original stance, mapped to the rig. Toggle the reference to compare.',
    },
    idle: {
      label: 'Idle',
      duration: 3.2,
      description: 'The relaxed line-up stance: a slow breath, hanging arms, head counter-motion.',
    },
    walk: {
      label: 'Walk',
      duration: 1,
      description:
        'A bouncy strut that passes through Chet’s stride, with push-off heel and arm lag.',
    },
    punch: {
      label: 'Punch',
      duration: 1.2,
      description: 'Wind-up from the stance, a lunging straight, then recovery to guard.',
    },
  }

/**
 * Poses are absolute world headings per bone (degrees). Downward limbs: positive swings the tip
 * toward the viewer's left (behind the right-facing dweller). Upright bones (spine, head): positive
 * leans forward. Feet: 0 is flat on the floor, positive raises the heel.
 */
type Headings = Record<BoneId, number>
const TAU = Math.PI * 2
const BIND_HEADINGS = Object.fromEntries(
  bodyParts.map((bone) => [bone.id, bindHeading(bone.id)])
) as Headings
// Relaxed standing pose from the legendary dweller line-up: feet apart, arms hanging slightly out.
const REST_HEADINGS: Headings = {
  pelvis: 0,
  spine: 0,
  head: 0,
  frontUpperArm: 10,
  frontForearm: -4,
  frontHand: -24,
  backUpperArm: -14,
  backForearm: -16,
  backHand: -25,
  frontThigh: -8,
  frontShin: -8,
  frontFoot: 0,
  backThigh: 8,
  backShin: 8,
  backFoot: 0,
}
const HAND_REST = { frontHand: -20, backHand: -9 }
// The far arm swings about a forward-leaning centre so perspective keeps it clear of the torso.
const ARM_CENTER = { front: 6.75, back: -1.4 }
const ARM_SWING = { front: 21.65, back: 14 }

function toRelative(headings: Headings): JointAngles {
  return Object.fromEntries(
    RIG_BONES.map((bone) => [
      bone.id,
      headings[bone.id] - (bone.parent ? headings[bone.parent] : 0),
    ])
  )
}

/** One leg over its own stride phase: 0 = fully back (push-off), π = fully forward (contact). */
function strideLeg(side: 'front' | 'back', phi: number): Partial<Headings> {
  const cos = Math.cos(phi)
  const swing = Math.max(0, Math.sin(phi))
  const thigh = 2.5 + 25.5 * cos
  const knee = 9 - 17 * cos + 30 * swing * swing
  const heel = 14 * Math.max(0, cos) ** 3
  return {
    [`${side}Thigh`]: thigh,
    [`${side}Shin`]: thigh + knee,
    [`${side}Foot`]: heel,
  } as Partial<Headings>
}

/** One arm, same phase convention: Vault Boy forearms stay near vertical and lag the upper arm. */
function strideArm(side: 'front' | 'back', phi: number): Partial<Headings> {
  const upper = ARM_CENTER[side] + ARM_SWING[side] * Math.cos(phi)
  const elbow = -17 - 14 * Math.cos(phi - 0.5)
  const wrist = HAND_REST[`${side}Hand`] + 5 * Math.sin(phi)
  return {
    [`${side}UpperArm`]: upper,
    [`${side}Forearm`]: upper + elbow,
    [`${side}Hand`]: upper + elbow + wrist,
  } as Partial<Headings>
}

const punchKeys: Array<{ time: number; x: number; headings: Partial<Headings> }> = [
  { time: 0, x: 0, headings: {} },
  {
    time: 0.22,
    x: -8,
    headings: {
      spine: -6,
      head: 4,
      frontUpperArm: 32,
      frontForearm: -70,
      frontHand: -70,
      backUpperArm: -24,
      backForearm: -82,
      backHand: -82,
      frontThigh: -4,
      frontShin: 0,
      backThigh: 14,
      backShin: 10,
    },
  },
  {
    time: 0.42,
    x: 14,
    headings: {
      spine: 9,
      head: -6,
      frontUpperArm: -80,
      frontForearm: -86,
      frontHand: -86,
      backUpperArm: 22,
      backForearm: -40,
      backHand: -40,
      frontThigh: -22,
      frontShin: -6,
      backThigh: 20,
      backShin: 16,
      backFoot: 32,
    },
  },
  {
    time: 0.66,
    x: 6,
    headings: {
      spine: 4,
      head: -2,
      frontUpperArm: -40,
      frontForearm: -92,
      frontHand: -92,
      backUpperArm: 10,
      backForearm: -60,
      backHand: -60,
      frontThigh: -14,
      frontShin: -8,
      backThigh: 14,
      backShin: 12,
      backFoot: 10,
    },
  },
  { time: 1, x: 0, headings: {} },
]

export function sampleRigClip(
  clip: RigClip,
  phase: number
): { angles: JointAngles; x: number; y: number } {
  const t = Math.max(0, Math.min(1, phase))
  if (clip === 'bind') return { x: 0, y: 0, angles: toRelative(BIND_HEADINGS) }
  if (clip === 'idle') {
    const breath = Math.sin(t * TAU)
    return {
      x: 0,
      y: breath * 1.4,
      angles: toRelative({
        ...REST_HEADINGS,
        spine: breath * 1.2,
        head: -breath * 0.6,
        frontUpperArm: REST_HEADINGS.frontUpperArm + breath * 2,
        frontForearm: REST_HEADINGS.frontForearm + breath * 2,
        frontHand: REST_HEADINGS.frontHand + breath * 2,
        backUpperArm: REST_HEADINGS.backUpperArm - breath * 2,
        backForearm: REST_HEADINGS.backForearm - breath * 2,
        backHand: REST_HEADINGS.backHand - breath * 2,
      }),
    }
  }
  if (clip === 'walk') {
    const phi = t * TAU
    const bounce = (1 - Math.cos(2 * phi)) / 2
    return {
      x: 0,
      y: -5 * bounce,
      angles: toRelative({
        ...REST_HEADINGS,
        spine: 5 + 1.2 * Math.sin(2 * phi),
        head: 1 - 1.2 * Math.sin(2 * phi),
        ...strideLeg('back', phi),
        ...strideLeg('front', phi + Math.PI),
        ...strideArm('front', phi),
        ...strideArm('back', phi + Math.PI),
      }),
    }
  }
  const index = punchKeys.findIndex((key) => key.time >= t)
  const next = punchKeys[Math.max(1, index)]!
  const previous = punchKeys[Math.max(1, index) - 1]!
  const fraction = (t - previous.time) / (next.time - previous.time)
  const eased = fraction * fraction * (3 - 2 * fraction)
  const headings = { ...REST_HEADINGS }
  for (const bone of RIG_BONES) {
    const from = previous.headings[bone.id] ?? REST_HEADINGS[bone.id]
    const to = next.headings[bone.id] ?? REST_HEADINGS[bone.id]
    headings[bone.id] = from * (1 - eased) + to * eased
  }
  return { angles: toRelative(headings), x: previous.x * (1 - eased) + next.x * eased, y: 0 }
}

function rotate([x, y]: Point, angle: number): Point {
  const radians = (angle * Math.PI) / 180
  return [
    x * Math.cos(radians) - y * Math.sin(radians),
    x * Math.sin(radians) + y * Math.cos(radians),
  ]
}

export function resolveRig(
  clip: RigClip,
  phase: number,
  adjustments: JointAngles = {},
  sprites: SpriteOverrides = {}
): RigJoint[] {
  const pose = sampleRigClip(clip, phase)
  const joints = new Map<BoneId, RigJoint>()
  for (const bone of RIG_BONES) {
    const parent = bone.parent ? joints.get(bone.parent)! : undefined
    const [dx, dy] = rotate(bone.offset, parent?.angle ?? 0)
    const x = (parent?.x ?? pose.x) + dx
    const y = (parent?.y ?? pose.y) + dy
    const angle = (parent?.angle ?? 0) + (pose.angles[bone.id] ?? 0) + (adjustments[bone.id] ?? 0)
    const [tx, ty] = rotate(bone.end, angle)
    const sprite =
      clip === 'punch' && (bone.id === 'frontHand' || bone.id === 'backHand')
        ? {
            sheet: 'hands' as const,
            crop: [96, 4, 54, 43] as const,
            frame: [bone.id === 'frontHand' ? -7.44 : -26.04, -17.36, 33.48, 26.66] as const,
            flipX: bone.id === 'frontHand',
            rotation: bone.id === 'frontHand' ? 90 : -90,
          }
        : bone.sprite
    joints.set(bone.id, {
      ...bone,
      sprite: sprites[bone.id] ?? sprite,
      x,
      y,
      angle,
      tip: [x + tx, y + ty],
    })
  }
  return [...joints.values()]
}
