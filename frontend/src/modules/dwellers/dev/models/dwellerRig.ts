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
  sprite: {
    sheet: 'suit' | 'head' | 'hands'
    crop: Rect
    frame: Rect
    flipX?: boolean
    rotation?: number
  }
}
export interface RigJoint extends Bone {
  x: number
  y: number
  angle: number
  tip: Point
}

export const RIG_BONES: readonly Bone[] = [
  {
    id: 'pelvis',
    label: 'Pelvis',
    parent: null,
    offset: [200, 295],
    end: [0, -12],
    layer: 3,
    sprite: { sheet: 'suit', crop: [397, 109, 83, 82], frame: [-30, -20, 60, 55] },
  },
  {
    id: 'spine',
    label: 'Spine',
    parent: 'pelvis',
    offset: [0, -6],
    end: [0, -96],
    layer: 4,
    sprite: { sheet: 'suit', crop: [157, 18, 86, 104], frame: [-43, -101, 86, 108], flipX: true },
  },
  {
    id: 'head',
    label: 'Head',
    parent: 'spine',
    offset: [0, -96],
    end: [0, -95],
    layer: 8,
    sprite: { sheet: 'head', crop: [0, 0, 165, 196], frame: [-53, -126, 110, 131] },
  },
  {
    id: 'backUpperArm',
    label: 'Back shoulder · left arm',
    parent: 'spine',
    offset: [33, -82],
    end: [0, 49],
    layer: 1,
    sprite: { sheet: 'suit', crop: [330, 13, 36, 90], frame: [-14, -8, 28, 66] },
  },
  {
    id: 'backForearm',
    label: 'Back elbow · left arm',
    parent: 'backUpperArm',
    offset: [0, 49],
    end: [0, 43],
    layer: 1,
    sprite: { sheet: 'suit', crop: [334, 110, 36, 72], frame: [-13, -8, 26, 57] },
  },
  {
    id: 'backHand',
    label: 'Back wrist · left arm',
    parent: 'backForearm',
    offset: [0, 43],
    end: [0, 15],
    layer: 1,
    sprite: {
      sheet: 'hands',
      crop: [96, 4, 54, 43],
      frame: [-24.5, -15.5, 27, 21.5],
      rotation: -110,
    },
  },
  {
    id: 'frontUpperArm',
    label: 'Front shoulder · right arm',
    parent: 'spine',
    offset: [-33, -82],
    end: [0, 49],
    layer: 7,
    sprite: { sheet: 'suit', crop: [283, 28, 31, 73], frame: [-14, -8, 28, 63] },
  },
  {
    id: 'frontForearm',
    label: 'Front elbow · right arm',
    parent: 'frontUpperArm',
    offset: [0, 49],
    end: [0, 43],
    layer: 7,
    sprite: { sheet: 'suit', crop: [279, 110, 31, 70], frame: [-13, -8, 26, 57] },
  },
  {
    id: 'frontHand',
    label: 'Front wrist · right arm',
    parent: 'frontForearm',
    offset: [0, 43],
    end: [0, 15],
    layer: 7,
    sprite: {
      sheet: 'hands',
      crop: [96, 4, 54, 43],
      frame: [-2.5, -15.5, 27, 21.5],
      flipX: true,
      rotation: 110,
    },
  },
  {
    id: 'backThigh',
    label: 'Back hip',
    parent: 'pelvis',
    offset: [-16, 9],
    end: [0, 68],
    layer: 0,
    sprite: { sheet: 'suit', crop: [19, 19, 49, 101], frame: [-17, -8, 34, 83] },
  },
  {
    id: 'backShin',
    label: 'Back knee',
    parent: 'backThigh',
    offset: [0, 68],
    end: [0, 63],
    layer: 0,
    sprite: { sheet: 'suit', crop: [22, 132, 41, 78], frame: [-15, -8, 30, 78] },
  },
  {
    id: 'backFoot',
    label: 'Back ankle',
    parent: 'backShin',
    offset: [0, 63],
    end: [24, 7],
    layer: 0,
    sprite: { sheet: 'suit', crop: [378, 213, 53, 33], frame: [-15, -4, 44, 23], flipX: true },
  },
  {
    id: 'frontThigh',
    label: 'Front hip',
    parent: 'pelvis',
    offset: [16, 9],
    end: [0, 68],
    layer: 2,
    sprite: { sheet: 'suit', crop: [80, 18, 48, 98], frame: [-17, -8, 34, 83] },
  },
  {
    id: 'frontShin',
    label: 'Front knee',
    parent: 'frontThigh',
    offset: [0, 68],
    end: [0, 63],
    layer: 2,
    sprite: { sheet: 'suit', crop: [85, 135, 42, 79], frame: [-15, -8, 30, 78] },
  },
  {
    id: 'frontFoot',
    label: 'Front ankle',
    parent: 'frontShin',
    offset: [0, 63],
    end: [24, 7],
    layer: 2,
    sprite: { sheet: 'suit', crop: [447, 213, 62, 34], frame: [-15, -4, 44, 23], flipX: true },
  },
]

export const RIG_CLIPS: Record<RigClip, { label: string; duration: number; description: string }> =
  {
    bind: {
      label: 'Bind pose',
      duration: 1,
      description: 'Inspect joint pivots and the attachment hierarchy.',
    },
    idle: {
      label: 'Idle',
      duration: 3,
      description: 'A slow breath, small shoulder shifts, and head counter-motion.',
    },
    walk: {
      label: 'Walk',
      duration: 1.1,
      description: 'Opposing limbs, knee flexion, and ankle compensation.',
    },
    punch: {
      label: 'Punch',
      duration: 1.2,
      description: 'Anticipation, extension, contact, and recovery.',
    },
  }

const punchKeys: Array<{ time: number; x: number; angles: JointAngles }> = [
  { time: 0, x: 0, angles: { frontUpperArm: -8, frontForearm: -12, backUpperArm: 12 } },
  {
    time: 0.23,
    x: -8,
    angles: {
      spine: -8,
      frontUpperArm: 32,
      frontForearm: -95,
      backUpperArm: -20,
      backForearm: -35,
    },
  },
  {
    time: 0.42,
    x: 12,
    angles: {
      spine: 11,
      frontUpperArm: -104,
      frontForearm: -7,
      backUpperArm: 22,
      backForearm: -35,
      head: -8,
    },
  },
  {
    time: 0.65,
    x: 6,
    angles: { spine: 6, frontUpperArm: -65, frontForearm: -35, backUpperArm: 18, head: -4 },
  },
  { time: 1, x: 0, angles: { frontUpperArm: -8, frontForearm: -12, backUpperArm: 12 } },
]

export function sampleRigClip(
  clip: RigClip,
  phase: number
): { angles: JointAngles; x: number; y: number } {
  const t = Math.max(0, Math.min(1, phase))
  const wave = Math.sin(t * Math.PI * 2)
  if (clip === 'bind') return { angles: {}, x: 0, y: 0 }
  if (clip === 'idle')
    return {
      x: 0,
      y: wave * 1.4,
      angles: {
        spine: wave * 1.2,
        head: -wave * 1.8,
        frontUpperArm: -8 + wave * 2,
        frontForearm: -8,
        backUpperArm: 10 - wave * 2,
        backForearm: -5,
      },
    }
  if (clip === 'walk') {
    const frontKnee = Math.max(0, -wave) * 38
    const backKnee = Math.max(0, wave) * 38
    return {
      x: 0,
      y: -Math.abs(wave) * 4,
      angles: {
        spine: 2,
        head: -2,
        frontThigh: wave * 28,
        backThigh: -wave * 28,
        frontShin: frontKnee,
        backShin: backKnee,
        frontFoot: -wave * 28 - frontKnee,
        backFoot: wave * 28 - backKnee,
        frontUpperArm: -wave * 24 - 6,
        backUpperArm: wave * 24 + 6,
        frontForearm: -12,
        backForearm: -12,
      },
    }
  }
  const index = punchKeys.findIndex((key) => key.time >= t)
  const next = punchKeys[Math.max(1, index)]!
  const previous = punchKeys[Math.max(1, index) - 1]!
  const fraction = (t - previous.time) / (next.time - previous.time)
  const eased = fraction * fraction * (3 - 2 * fraction)
  const angles: JointAngles = {}
  for (const bone of RIG_BONES)
    angles[bone.id] =
      (previous.angles[bone.id] ?? 0) * (1 - eased) + (next.angles[bone.id] ?? 0) * eased
  return { angles, x: previous.x * (1 - eased) + next.x * eased, y: 0 }
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
  adjustments: JointAngles = {}
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
    joints.set(bone.id, { ...bone, x, y, angle, tip: [x + tx, y + ty] })
  }
  return [...joints.values()]
}
