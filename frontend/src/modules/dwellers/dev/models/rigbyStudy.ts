import { readSkeletonJson, type Pose, type Skeleton } from '../../../../../vendor/rigby2d'
import outfitsUrl from '../assets/rigby/outfits.png'
import femaleOutfitsUrl from '../assets/rigby/outfits-female.png'
import accessoriesUrl from '../assets/rigby/accessories.png'
import weaponsUrl from '../assets/rigby/weapons.png'
import quarterHeadUrl from '../assets/chet-head.webp'
import femaleHeadUrl from '../assets/amata-head.png'

export type StudyBody = 'male' | 'female'
export type StudyClip = 'idle' | 'walk' | 'attack'
export type StudyWeapon = 'none' | 'pistol' | 'rifle'
export type StudyHat = 'none' | 'fedora' | 'cowboy'
type Rect = readonly [number, number, number, number]
type Region = {
  page: 'outfits.png' | 'outfits-female.png' | 'accessories.png' | 'weapons.png'
  rect: Rect
}

export const CLIP_SECONDS: Record<StudyClip, number> = { idle: 3, walk: 1.2, attack: 1.5 }
export const ATLAS_IMAGES = {
  'outfits.png': outfitsUrl,
  'outfits-female.png': femaleOutfitsUrl,
  'accessories.png': accessoriesUrl,
  'weapons.png': weaponsUrl,
}
export const HEAD_IMAGES = {
  'head-quarter': quarterHeadUrl,
  'head-amata': femaleHeadUrl,
}

// Original atlas coordinates. No repacking, repainting, or destructive source edits.
const outfitRects: Record<string, Record<string, Rect>> = {
  vault: {
    torso: [717, 18, 86, 104],
    pelvis: [955, 106, 88, 86],
    upperArm: [840, 29, 37, 73],
    forearm: [835, 111, 39, 69],
    thigh: [578, 18, 53, 101],
    shin: [580, 131, 44, 80],
    foot: [937, 212, 55, 35],
  },
  wasteland: {
    torso: [1276, 13, 87, 110],
    pelvis: [1519, 112, 80, 81],
    upperArm: [1401, 28, 38, 75],
    forearm: [1394, 112, 41, 72],
    thigh: [1138, 18, 53, 101],
    shin: [1140, 131, 44, 81],
    foot: [1496, 208, 56, 40],
  },
}
const femaleRects: Record<string, Record<string, Rect>> = {
  vault: {
    torso: [575, 37, 83, 104],
    upperArm: [726, 12, 29, 66],
    forearm: [731, 95, 29, 59],
    thigh: [448, 24, 45, 87],
    shin: [453, 121, 33, 77],
    foot: [435, 209, 37, 29],
  },
}
function regionsFor(prefix: string, parts: Record<string, Rect>, page: Region['page']) {
  return Object.entries(parts).map(([part, rect]) => [`${prefix}-${part}`, { page, rect }] as const)
}
export const REGIONS: Record<string, Region> = Object.fromEntries([
  ...Object.entries(outfitRects).flatMap(([outfit, parts]) =>
    regionsFor(outfit, parts, 'outfits.png')
  ),
  ...Object.entries(femaleRects).flatMap(([outfit, parts]) =>
    regionsFor(`female-${outfit}`, parts, 'outfits-female.png')
  ),
])
Object.assign(REGIONS, {
  hand: { page: 'accessories.png', rect: [17, 1640, 61, 47] },
  fist: { page: 'accessories.png', rect: [96, 1581, 51, 44] },
  fedora: { page: 'accessories.png', rect: [484, 578, 108, 53] },
  cowboy: { page: 'accessories.png', rect: [718, 578, 116, 65] },
  pistol: { page: 'weapons.png', rect: [1255, 20, 164, 102] },
  rifle: { page: 'weapons.png', rect: [921, 238, 295, 84] },
})

const bodyAtlas = Object.entries(ATLAS_IMAGES)
  .map(([page]) =>
    [
      page,
      'filter: Linear,Linear',
      ...Object.entries(REGIONS)
        .filter(([, r]) => r.page === page)
        .flatMap(([name, r]) => [name, `bounds: ${r.rect.join(',')}`]),
    ].join('\n')
  )
  .join('\n\n')

// Loose head pages are listed in exports too. The preview loads these through imageTextures.
export const ATLAS_TEXT =
  bodyAtlas +
  '\n\n' +
  [
    ['chet-head.webp', 'head-quarter', 94, 96],
    ['amata-head.png', 'head-amata', 111, 100],
  ]
    .map(
      ([page, name, width, height]) =>
        `${page}\nfilter: Linear,Linear\n${name}\nbounds: 0,0,${width},${height}`
    )
    .join('\n\n')

type BoneJson = { name: string; parent?: string; x?: number; y?: number; rotation?: number }
type AttachmentJson = {
  path: string
  x: number
  y: number
  width: number
  height: number
  rotation?: number
  scaleX?: number
  scaleY?: number
}

/** A single three-quarter setup shared by every clip. */
export function createStudySkeleton(body: StudyBody): Skeleton {
  const female = body === 'female'
  const width = 0.86
  const shoulder = 38 * width * (female ? 0.95 : 1)
  const hip = 19 * width * (female ? 1.1 : 1)
  const thighWidth = female ? 37 : 39
  const thighHeight = female ? 80 : 85
  const shinWidth = female ? 30 : 34
  const shinHeight = female ? 74 : 72
  const footWidth = female ? 32 : 45
  const footHeight = female ? 24 : 26
  const pelvisWidth = female ? 80 * width : 90 * width
  const pelvisHeight = female ? 57 : 65
  const upperArmWidth = female ? 25 : 32
  const upperArmHeight = female ? 61 : 67
  const forearmWidth = female ? 20 : 27
  const forearmHeight = female ? 46 : 54
  const torsoWidth = female ? 81 : 98 * width
  const bones: BoneJson[] = [
    { name: 'root' },
    { name: 'pelvis', parent: 'root', y: 160 },
    { name: 'torso', parent: 'pelvis' },
    { name: 'head', parent: 'torso', y: 97 },
  ]
  for (const [side, sign] of [
    ['back', 1],
    ['front', -1],
  ] as const) {
    bones.push(
      { name: `${side}Thigh`, parent: 'pelvis', x: sign * hip, y: -13 },
      { name: `${side}Shin`, parent: `${side}Thigh`, y: -70 },
      { name: `${side}Foot`, parent: `${side}Shin`, y: -60 },
      { name: `${side}Arm`, parent: 'torso', x: sign * shoulder, y: 82, rotation: sign * 6 },
      { name: `${side}Forearm`, parent: `${side}Arm`, y: -50, rotation: side === 'front' ? 1 : 5 },
      { name: `${side}Hand`, parent: `${side}Forearm`, y: -45 }
    )
  }
  bones.push({ name: 'weapon', parent: 'frontHand', y: -9 })
  const slots: Array<{ name: string; bone: string; attachment: string | null }> = []
  const defaults: Record<string, Record<string, AttachmentJson>> = {}
  const skins: Record<string, Record<string, Record<string, AttachmentJson>>> = female
    ? { 'female-vault': {} }
    : { vault: {}, wasteland: {} }
  function slot(
    name: string,
    bone: string,
    attachments: Record<string, AttachmentJson>,
    active: string | null
  ) {
    slots.push({ name, bone, attachment: active })
    defaults[name] = attachments
  }
  function part(
    name: string,
    bone: string,
    partName: string,
    x: number,
    y: number,
    w: number,
    h: number,
    flip = false,
    rotation = 0
  ) {
    slot(name, bone, {}, 'part')
    for (const outfit of Object.keys(skins)) {
      skins[outfit]![name] = {
        part: {
          path: `${outfit}-${partName}`,
          x,
          y,
          width: w,
          height: h,
          scaleX: flip ? -1 : 1,
          rotation,
        },
      }
    }
  }
  function leg(side: string) {
    part(
      `${side}Thigh`,
      `${side}Thigh`,
      'thigh',
      0,
      -30,
      thighWidth,
      thighHeight,
      female,
      female ? 0 : 3
    )
    part(`${side}Shin`, `${side}Shin`, 'shin', 0, -25, shinWidth, shinHeight, female)
    part(`${side}Foot`, `${side}Foot`, 'foot', 8, -6, footWidth, footHeight, true)
  }
  function arm(side: string, flipOpenPalm = false) {
    const upperArmX = side === 'back' ? -4 : 0
    part(`${side}Arm`, `${side}Arm`, 'upperArm', upperArmX, -22, upperArmWidth, upperArmHeight)
    part(`${side}Forearm`, `${side}Forearm`, 'forearm', 0, -20, forearmWidth, forearmHeight, true)
    slot(
      `${side}Hand`,
      `${side}Hand`,
      {
        open: {
          path: 'hand',
          x: 0,
          y: flipOpenPalm ? -4 : -10,
          width: 32,
          height: 25,
          rotation: -90,
          scaleY: -1,
        },
        fist: {
          path: 'fist',
          x: flipOpenPalm ? 2 : 0,
          y: -10,
          width: 26,
          height: 24,
          rotation: 90,
          scaleY: flipOpenPalm ? -1 : 1,
        },
      },
      'open'
    )
  }
  arm('back')
  leg('back')
  // Female Vault 101 torso art includes the yellow hip/waist, so it has no separate pelvis sprite.
  if (!female) part('pelvis', 'pelvis', 'pelvis', 0, -4, pelvisWidth, pelvisHeight)
  leg('front')
  part('torso', 'torso', 'torso', 0, 48, torsoWidth, 113, true)
  slot(
    'head',
    'head',
    {
      head: {
        path: female ? 'head-amata' : 'head-quarter',
        x: 0,
        y: female ? 33 : 41,
        width: 94,
        height: female ? 85 : 101,
      },
    },
    'head'
  )
  slot(
    'hat',
    'head',
    {
      // Hat art is authored facing left; mirror it to face the same way as the body.
      // The female head art is shorter, so its hats sit lower to keep the same overlap.
      fedora: { path: 'fedora', x: 0, y: female ? 69 : 85, width: 104, height: 51, scaleX: -1 },
      cowboy: { path: 'cowboy', x: 0, y: female ? 70 : 86, width: 119, height: 63, scaleX: -1 },
    },
    null
  )
  arm('front', true)
  slot(
    'weapon',
    'weapon',
    {
      pistol: { path: 'pistol', x: 20, y: 10, width: 72, height: 45, scaleX: -1 },
      rifle: { path: 'rifle', x: 26, y: 10, width: 140, height: 40, scaleX: -1 },
    },
    null
  )
  // Fingers cover the grip, independent of bone hierarchy.
  const handIndex = slots.findIndex((s) => s.name === 'frontHand')
  slots.push(...slots.splice(handIndex, 1))
  const rotate = (values: number[], duration: number) =>
    values.map((angle, i) => ({ time: (i * duration) / (values.length - 1), angle }))
  const walk: Record<string, unknown> = {}
  for (const [side, sign] of [
    ['front', 1],
    ['back', -1],
  ] as const) {
    walk[`${side}Thigh`] = { rotate: rotate([-25 * sign, 0, 25 * sign, 0, -25 * sign], 1.2) }
    walk[`${side}Shin`] = { rotate: rotate(sign > 0 ? [5, 8, 12, 42, 5] : [12, 42, 5, 8, 12], 1.2) }
    walk[`${side}Foot`] = { rotate: rotate([12 * sign, 0, -12 * sign, 0, 12 * sign], 1.2) }
    walk[`${side}Arm`] = { rotate: rotate([20 * sign, 0, -20 * sign, 0, 20 * sign], 1.2) }
    walk[`${side}Forearm`] = { rotate: rotate([8, 18, 8, 0, 8], 1.2) }
  }
  // Small hand drift so a held weapon does not look frozen while the legs walk.
  walk.frontHand = { rotate: rotate([0, 2, 0, -2, 0], 1.2) }
  walk.backHand = { rotate: rotate([0, -2, 0, 2, 0], 1.2) }
  // The three-quarter art faces right; mirror the authored stride so the swing foot travels right.
  for (const track of Object.values(walk) as Array<{ rotate: Array<{ angle: number }> }>) {
    for (const keyframe of track.rotate) keyframe.angle = -keyframe.angle
  }
  const animations = {
    idle: {
      bones: {
        // Subtle weight shift: the pelvis rocks while the thighs counter-rotate.
        pelvis: { rotate: rotate([0, 1.5, 0], 3) },
        frontThigh: { rotate: rotate([0, -1.5, 0], 3) },
        backThigh: { rotate: rotate([0, -1.5, 0], 3) },
        torso: { translate: [{ y: 0 }, { time: 1.5, y: 2 }, { time: 3, y: 0 }] },
        head: { rotate: rotate([-1, 1, -1], 3) },
        frontArm: { rotate: rotate([0, 2, 0], 3) },
        backArm: { rotate: rotate([0, -2, 0], 3) },
      },
    },
    walk: {
      bones: {
        ...walk,
        pelvis: {
          translate: [
            { y: 0 },
            { time: 0.3, y: 4 },
            { time: 0.6, y: 0 },
            { time: 0.9, y: 4 },
            { time: 1.2, y: 0 },
          ],
        },
      },
    },
    attack: {
      bones: {
        torso: { rotate: rotate([0, -5, 3, 0, 0], 1.5) },
        frontArm: { rotate: rotate([0, 60, 78, 65, 0], 1.5) },
        frontForearm: { rotate: rotate([0, 35, 10, 25, 0], 1.5) },
        backArm: { rotate: rotate([0, 20, 25, 15, 0], 1.5) },
        head: { rotate: rotate([0, 4, -3, 0, 0], 1.5) },
      },
    },
  }
  const { skeleton, warnings } = readSkeletonJson({
    skeleton: { spine: '3.8', name: `dweller-quarter-${body}` },
    bones,
    slots,
    skins: { default: defaults, ...skins },
    animations,
  })
  if (warnings.length) throw new Error(warnings.join('; '))
  skeleton.skin = female ? 'female-vault' : 'vault'
  return skeleton
}

/** Analytic two-joint correction that places the support hand on the rifle foregrip. */
export function aimSupportHand(skeleton: Skeleton, pose: Pose, mirrored: boolean) {
  const index = (name: string) => skeleton.bones.findIndex((b) => b.name === name)
  const upper = index('backArm')
  const lower = index('backForearm')
  const weapon = index('weapon')
  const shoulder = pose.world[upper]!
  const gun = pose.world[weapon]!
  const targetX = gun.tx + gun.a * 52 + gun.c * 5
  const targetY = gun.ty + gun.b * 52 + gun.d * 5
  const dx = targetX - shoulder.tx
  const dy = targetY - shoulder.ty
  const scale = Math.hypot(shoulder.a, shoulder.b)
  const a = 50 * scale
  const b = 45 * scale
  const distance = Math.max(Math.abs(a - b) + 0.01, Math.min(a + b - 0.01, Math.hypot(dx, dy)))
  const reflected = mirrored ? -1 : 1
  const elbow = Math.acos((distance * distance - a * a - b * b) / (2 * a * b)) * reflected
  const angle = Math.atan2(dy, dx) - Math.atan2(b * Math.sin(elbow), a + b * Math.cos(elbow))
  const torso = pose.world[index('torso')]!
  const determinant = torso.a * torso.d - torso.b * torso.c
  const localX = (torso.d * Math.cos(angle) - torso.c * Math.sin(angle)) / determinant
  const localY = (-torso.b * Math.cos(angle) + torso.a * Math.sin(angle)) / determinant
  pose.local[upper]!.rotation = (Math.atan2(localY, localX) * 180) / Math.PI + 90
  pose.local[lower]!.rotation = ((elbow * 180) / Math.PI) * reflected
  pose.updateWorld(skeleton)
}
