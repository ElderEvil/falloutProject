import { readSkeletonJson, type Skeleton } from '../../../../../vendor/rigby2d'
import outfitsUrl from '../assets/rigby/outfits.png'
import accessoriesUrl from '../assets/rigby/accessories.png'
import weaponsUrl from '../assets/rigby/weapons.png'
import frontHeadUrl from '../assets/rigby/front-head.svg'
import sideHeadUrl from '../assets/rigby/side-head.svg'
import quarterHeadUrl from '../assets/chet-head.webp'

export type StudyView = 'front' | 'quarter' | 'side'
export type StudyBody = 'human' | 'bulky'
export type StudyClip = 'idle' | 'walk' | 'attack'
export type StudyWeapon = 'none' | 'pistol' | 'rifle'
export type StudyHat = 'none' | 'fedora' | 'cowboy'
type Rect = readonly [number, number, number, number]
type Region = { page: 'outfits.png' | 'accessories.png' | 'weapons.png'; rect: Rect }

export const CLIP_SECONDS: Record<StudyClip, number> = { idle: 3, walk: 1.2, attack: 1.5 }
export const VIEW_LABELS: Record<StudyView, string> = {
  front: 'Front',
  quarter: 'Three-quarter',
  side: 'Side',
}
export const ATLAS_IMAGES = {
  'outfits.png': outfitsUrl,
  'accessories.png': accessoriesUrl,
  'weapons.png': weaponsUrl,
}
export const HEAD_IMAGES = {
  'head-front': frontHeadUrl,
  'head-quarter': quarterHeadUrl,
  'head-side': sideHeadUrl,
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
export const REGIONS: Record<string, Region> = Object.fromEntries(
  Object.entries(outfitRects).flatMap(([outfit, parts]) =>
    Object.entries(parts).map(([part, rect]) => [
      `${outfit}-${part}`,
      { page: 'outfits.png', rect },
    ])
  )
)
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
    ['front-head.svg', 'head-front', 100, 110],
    ['chet-head.webp', 'head-quarter', 94, 96],
    ['side-head.svg', 'head-side', 100, 110],
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
}

/** Three projected setups share the same bone names and clips. Dedicated view art remains future work. */
export function createStudySkeleton(view: StudyView, body: StudyBody): Skeleton {
  const width = { front: 1, quarter: 0.86, side: 0.59 }[view]
  const broad = body === 'bulky' ? 1.32 : 1
  const shoulder = (view === 'side' ? 9 : 38 * width) * broad
  const hip = (view === 'side' ? 5 : 19 * width) * broad
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
      { name: `${side}Forearm`, parent: `${side}Arm`, y: -50, rotation: 5 },
      { name: `${side}Hand`, parent: `${side}Forearm`, y: -45 }
    )
  }
  bones.push({ name: 'weapon', parent: 'frontHand', y: -9 })
  const slots: Array<{ name: string; bone: string; attachment: string | null }> = []
  const defaults: Record<string, Record<string, AttachmentJson>> = {}
  const skins: Record<string, Record<string, Record<string, AttachmentJson>>> = {
    vault: {},
    wasteland: {},
  }
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
    flip = false
  ) {
    slot(name, bone, {}, 'part')
    for (const outfit of Object.keys(skins)) {
      skins[outfit]![name] = {
        part: { path: `${outfit}-${partName}`, x, y, width: w, height: h, scaleX: flip ? -1 : 1 },
      }
    }
  }
  function leg(side: string) {
    part(`${side}Thigh`, `${side}Thigh`, 'thigh', 0, -30, 39 * broad, 85)
    part(`${side}Shin`, `${side}Shin`, 'shin', 0, -25, 34 * broad, 72)
    part(`${side}Foot`, `${side}Foot`, 'foot', 8, -6, 45 * broad, 26, true)
  }
  function arm(side: string) {
    part(`${side}Arm`, `${side}Arm`, 'upperArm', 0, -22, 32 * broad, 67)
    part(`${side}Forearm`, `${side}Forearm`, 'forearm', 0, -20, 27 * broad, 54)
    slot(
      `${side}Hand`,
      `${side}Hand`,
      {
        open: { path: 'hand', x: 0, y: -10, width: 32, height: 25, rotation: -90 },
        fist: { path: 'fist', x: 0, y: -10, width: 26, height: 24, rotation: 90 },
      },
      'open'
    )
  }
  arm('back')
  leg('back')
  part('pelvis', 'pelvis', 'pelvis', 0, -4, 79 * width * broad, 58)
  leg('front')
  part('torso', 'torso', 'torso', 0, 48, 98 * width * broad, 113, true)
  slot(
    'head',
    'head',
    { head: { path: `head-${view}`, x: view === 'side' ? 5 : 0, y: 41, width: 94, height: 101 } },
    'head'
  )
  slot(
    'hat',
    'head',
    {
      fedora: { path: 'fedora', x: 0, y: 85, width: 104, height: 51 },
      cowboy: { path: 'cowboy', x: 0, y: 86, width: 119, height: 63 },
    },
    null
  )
  arm('front')
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
  const animations = {
    idle: {
      bones: {
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
    skeleton: { spine: '3.8', name: `dweller-${view}-${body}` },
    bones,
    slots,
    skins: { default: defaults, ...skins },
    animations,
  })
  if (warnings.length) throw new Error(warnings.join('; '))
  skeleton.skin = 'vault'
  return skeleton
}
