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

// Limb frames use uniform scaling; shoe heel/toe anchors are documented beside the assets.
const bodyParts: readonly Omit<Bone, 'offset' | 'end' | 'bindAngle'>[] = [
  {
    id: 'pelvis',
    label: 'Waist / pelvis',
    parent: null,
    layer: 3,
    sprite: { sheet: 'suit', crop: [397, 109, 83, 82], frame: [-54, -17, 97, 53] },
  },
  {
    id: 'spine',
    label: 'Spine',
    parent: 'pelvis',
    layer: 4,
    sprite: {
      sheet: 'suit',
      crop: [157, 18, 86, 104],
      frame: [-47.276, -104.505, 85, 126.5],
      rotation: 3,
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
      crop: [330, 13, 36, 90],
      frame: [-23.8327, -13.5817, 36.8654, 92.1634],
      rotation: 6.5,
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
      frame: [-12, -12.327, 25.2, 50.4],
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
      frame: [-4.65, -11.625, 44.175, 34.1],
      rotation: 90,
    },
  },
  {
    id: 'frontUpperArm',
    label: 'Front shoulder · right arm',
    parent: 'spine',
    layer: 7,
    sprite: {
      sheet: 'suit',
      crop: [283, 28, 31, 73],
      frame: [-17.9464, -26.0284, 34.0927, 80.2828],
      rotation: -8,
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
      frame: [-15, -13.487, 31, 70],
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
      frame: [-51, -15, 57, 44],
      flipX: true,
      rotation: -90,
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
      frame: [-17.5747, -4.2458, 43.1494, 88.9407],
      rotation: -2,
    },
  },
  {
    id: 'backShin',
    label: 'Back knee · left leg',
    parent: 'backThigh',
    layer: 0,
    sprite: {
      sheet: 'suit',
      crop: [22, 132, 41, 78],
      frame: [-12.0637, -1.4747, 37.1273, 70.6325],
      rotation: 7.5,
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
      frame: [-30.3, -32.2, 57.6, 117.6],
      rotation: 4,
    },
  },
  {
    id: 'frontShin',
    label: 'Front knee · right leg',
    parent: 'frontThigh',
    layer: 2,
    sprite: {
      sheet: 'suit',
      crop: [85, 135, 42, 79],
      frame: [-20, -2, 34.557, 65],
      rotation: 2.5,
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
const landmarks: Record<BoneId, { point: Point; tip: Point }> = {
  pelvis: { point: [74, 164], tip: [74, 152] },
  spine: { point: [74, 160], tip: [74, 87] },
  head: { point: [74, 87], tip: [74, 10] },
  backUpperArm: { point: [101, 105], tip: [113, 150] },
  backForearm: { point: [113, 150], tip: [119, 177] },
  backHand: { point: [119, 177], tip: [124, 202] },
  frontUpperArm: { point: [41, 106], tip: [21, 143] },
  frontForearm: { point: [21, 143], tip: [20, 185] },
  frontHand: { point: [20, 185], tip: [23, 205] },
  backThigh: { point: [84, 178], tip: [43, 218] },
  backShin: { point: [43, 218], tip: [30, 254] },
  backFoot: { point: [30, 254], tip: [40, 279] },
  frontThigh: { point: [53, 177], tip: [81, 224] },
  frontShin: { point: [81, 224], tip: [79, 268] },
  frontFoot: { point: [79, 268], tip: [109, 277] },
}
function bindHeading(id: BoneId): number {
  if (id === 'backFoot') return 55
  if (id === 'frontHand') return -17
  if (id === 'backHand') return -18
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
  if (clip === 'bind')
    return {
      x: 0,
      y: 0,
      angles: Object.fromEntries(RIG_BONES.map((bone) => [bone.id, bone.bindAngle])),
    }
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
        frontForearm: -36 - wave * 18,
        backForearm: -36 + wave * 18,
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
    joints.set(bone.id, { ...bone, sprite, x, y, angle, tip: [x + tx, y + ty] })
  }
  return [...joints.values()]
}
