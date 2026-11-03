import { describe, expect, it } from 'vite-plus/test'
import {
  Pose,
  readSkeletonJson,
  writeSkeletonJson,
  type Skeleton,
} from '../../../../../vendor/rigby2d'
import { createStudySkeleton } from '@/modules/dwellers/dev/models/rigbyStudy'

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
})
