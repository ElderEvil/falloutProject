import { describe, expect, it } from 'vitest'
import {
  Pose,
  readSkeletonJson,
  writeSkeletonJson,
  type Skeleton,
} from '../../../../../vendor/rigby2d'
import {
  REGIONS,
  aimSupportHand,
  createStudySkeleton,
} from '@/modules/dwellers/dev/models/rigbyStudy'

function liftedFootTravel(skeleton: Skeleton, footName: string) {
  const walk = skeleton.animations.find((animation) => animation.name === 'walk')!
  const foot = skeleton.bones.findIndex((bone) => bone.name === footName)
  const pose = new Pose(skeleton)
  const samples = Array.from({ length: 21 }, (_, index) => {
    pose.reset(skeleton)
    pose.apply(skeleton, walk, (index / 20) * walk.duration, 1)
    pose.updateWorld(skeleton)
    return { x: pose.world[foot]!.tx, y: pose.world[foot]!.ty }
  })
  const meanY = samples.reduce((sum, sample) => sum + sample.y, 0) / samples.length
  return samples.slice(1).reduce((sum, sample, index) => {
    const previous = samples[index]!
    return sample.y > meanY && previous.y > meanY ? sum + (sample.x - previous.x) : sum
  }, 0)
}

describe('Rigby2D study integration', () => {
  it('reloads the three-quarter rig with playable animation and equipment skins', () => {
    const original = createStudySkeleton('male')
    const { skeleton } = readSkeletonJson(
      JSON.parse(JSON.stringify(writeSkeletonJson(original).json))
    )
    const pose = new Pose(skeleton)
    const walk = skeleton.animations.find((a) => a.name === 'walk')!
    pose.apply(skeleton, walk, 0.3, 1)
    pose.updateWorld(skeleton)
    const before = pose.world.map((m) => ({ ...m }))
    skeleton.skin = 'vault'
    const torso = skeleton.slots.findIndex((s) => s.name === 'torso')
    expect(pose.slotAttachment(skeleton, torso)?.image).toBe('vault-torso')
    skeleton.skin = 'wasteland'
    expect(pose.slotAttachment(skeleton, torso)?.image).toBe('wasteland-torso')
    expect(pose.world).toEqual(before)
    pose.reset(skeleton)
    pose.apply(skeleton, walk, 0.9, 1)
    pose.updateWorld(skeleton)
    expect(pose.world).not.toEqual(before)
    expect(pose.world.every((m) => Number.isFinite(m.tx) && Number.isFinite(m.ty))).toBe(true)
  })

  it('walks toward the right with both feet', () => {
    const skeleton = createStudySkeleton('male')
    expect(liftedFootTravel(skeleton, 'frontFoot')).toBeGreaterThan(0)
    expect(liftedFootTravel(skeleton, 'backFoot')).toBeGreaterThan(0)
  })

  it('builds a playable Amata rig', () => {
    const skeleton = createStudySkeleton('female')
    const pose = new Pose(skeleton)
    const walk = skeleton.animations.find((animation) => animation.name === 'walk')!
    pose.apply(skeleton, walk, 0.3, 1)
    pose.updateWorld(skeleton)
    expect(skeleton.skin).toBe('female-vault')
    expect(
      pose.world.every((matrix) => Number.isFinite(matrix.tx) && Number.isFinite(matrix.ty))
    ).toBe(true)
  })

  it('draws the female hips from the female atlas instead of the male pelvis', () => {
    const female = createStudySkeleton('female')
    expect(female.slots.some((slot) => slot.name === 'pelvis')).toBe(false)
    expect(REGIONS['female-vault-pelvis']).toBeUndefined()
    expect(REGIONS['female-vault-torso']!.page).toBe('outfits-female.png')
    const male = createStudySkeleton('male')
    expect(male.slots.some((slot) => slot.name === 'pelvis')).toBe(true)
    expect(REGIONS['vault-pelvis']!.page).toBe('outfits.png')
  })

  it('round-trips equipment attachments through the exported rig', () => {
    const original = createStudySkeleton('male')
    original.slots.find((slot) => slot.name === 'hat')!.attachment = 'fedora'
    original.slots.find((slot) => slot.name === 'weapon')!.attachment = 'rifle'
    const { skeleton } = readSkeletonJson(
      JSON.parse(JSON.stringify(writeSkeletonJson(original).json))
    )
    expect(skeleton.slots.find((slot) => slot.name === 'hat')?.attachment).toBe('fedora')
    expect(skeleton.slots.find((slot) => slot.name === 'weapon')?.attachment).toBe('rifle')
  })

  it('mirrors the hat art and seats it lower on the shorter female head', () => {
    const hatsFor = (body: 'male' | 'female') => {
      const { json } = writeSkeletonJson(createStudySkeleton(body))
      const skins = json.skins as Array<{
        name: string
        attachments: Record<string, Record<string, { scaleX?: number; y?: number }>>
      }>
      return skins.find((skin) => skin.name === 'default')!.attachments.hat!
    }
    const maleHats = hatsFor('male')
    const femaleHats = hatsFor('female')
    expect(maleHats.fedora!.scaleX).toBe(-1)
    expect(maleHats.cowboy!.scaleX).toBe(-1)
    expect(femaleHats.fedora!.y).toBeLessThan(maleHats.fedora!.y!)
    expect(femaleHats.cowboy!.y).toBeLessThan(maleHats.cowboy!.y!)
  })

  it('keeps the mirrored support hand on the rifle foregrip', () => {
    const skeleton = createStudySkeleton('male')
    const pose = new Pose(skeleton)
    const walk = skeleton.animations.find((animation) => animation.name === 'walk')!
    const index = (name: string) => skeleton.bones.findIndex((bone) => bone.name === name)
    const gripDistance = (mirrored: boolean) => {
      pose.reset(skeleton)
      pose.apply(skeleton, walk, 0.3, 1)
      pose.local[0]!.scale_x = mirrored ? -1 : 1
      pose.updateWorld(skeleton)
      aimSupportHand(skeleton, pose, mirrored)
      const gun = pose.world[index('weapon')]!
      const hand = pose.world[index('backHand')]!
      const targetX = gun.tx + gun.a * 52 + gun.c * 5
      const targetY = gun.ty + gun.b * 52 + gun.d * 5
      return Math.hypot(hand.tx - targetX, hand.ty - targetY)
    }
    expect(gripDistance(false)).toBeLessThan(40)
    expect(gripDistance(true)).toBeLessThan(40)
    expect(gripDistance(true)).toBeCloseTo(gripDistance(false), 5)
  })

  it('shifts the lower body during idle', () => {
    const skeleton = createStudySkeleton('male')
    const pose = new Pose(skeleton)
    const idle = skeleton.animations.find((animation) => animation.name === 'idle')!
    const pelvisAngle = (time: number) => {
      pose.reset(skeleton)
      pose.apply(skeleton, idle, time, 1)
      pose.updateWorld(skeleton)
      const matrix = pose.world[skeleton.bones.findIndex((bone) => bone.name === 'pelvis')]!
      return Math.atan2(matrix.b, matrix.a)
    }
    expect(pelvisAngle(1.5)).not.toBeCloseTo(pelvisAngle(0), 2)
  })

  it('adds a small weapon-hand drift while walking', () => {
    const skeleton = createStudySkeleton('male')
    const pose = new Pose(skeleton)
    const walk = skeleton.animations.find((animation) => animation.name === 'walk')!
    const handAngle = (time: number) => {
      pose.reset(skeleton)
      pose.apply(skeleton, walk, time, 1)
      return pose.local[skeleton.bones.findIndex((bone) => bone.name === 'frontHand')]!.rotation
    }
    expect(handAngle(0.3)).not.toBeCloseTo(handAngle(0), 2)
    expect(Math.abs(handAngle(0.3))).toBeLessThan(4)
  })
})
