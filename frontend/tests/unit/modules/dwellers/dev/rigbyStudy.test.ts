import { describe, expect, it } from 'vite-plus/test'
import { Pose, readSkeletonJson, writeSkeletonJson } from '../../../../../vendor/rigby2d'
import { createStudySkeleton } from '@/modules/dwellers/dev/models/rigbyStudy'

describe('Rigby2D study integration', () => {
  it.each(['front', 'quarter', 'side'] as const)(
    'reloads %s with playable animation and equipment skins',
    (view) => {
      const original = createStudySkeleton(view, 'human')
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
    }
  )
})
