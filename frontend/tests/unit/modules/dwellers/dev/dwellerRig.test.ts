import { describe, expect, it } from 'vite-plus/test'
import {
  RIG_BONES,
  resolveRig,
  sampleRigClip,
  type RigClip,
} from '@/modules/dwellers/dev/models/dwellerRig'

describe('2D dweller skeleton', () => {
  it('defines each parent before its children with unique joint identities', () => {
    const seen = new Set<string>()
    for (const bone of RIG_BONES) {
      expect(seen.has(bone.id)).toBe(false)
      if (bone.parent) expect(seen.has(bone.parent)).toBe(true)
      seen.add(bone.id)
    }
    expect(seen.size).toBe(15)
  })

  it('places the foreground right arm on the viewer left and paints it over the torso', () => {
    const joints = resolveRig('bind', 0)
    const front = joints.find((joint) => joint.id === 'frontUpperArm')!
    const back = joints.find((joint) => joint.id === 'backUpperArm')!
    const torso = joints.find((joint) => joint.id === 'spine')!
    expect(front.x).toBeLessThan(back.x)
    expect(joints.find((joint) => joint.id === 'frontHand')!.x).toBeLessThan(
      joints.find((joint) => joint.id === 'backHand')!.x
    )
    expect(front.layer).toBeGreaterThan(torso.layer)
    expect(back.layer).toBeLessThan(torso.layer)
  })

  it('rotates the elbow and wrist with their shoulder, leaving the opposite arm intact', () => {
    const before = resolveRig('bind', 0)
    const after = resolveRig('bind', 0, { frontUpperArm: 90 })
    const shoulder = after.find((joint) => joint.id === 'frontUpperArm')!
    const elbow = after.find((joint) => joint.id === 'frontForearm')!
    const wrist = after.find((joint) => joint.id === 'frontHand')!
    expect(elbow.x).toBeCloseTo(shoulder.x - 49)
    expect(elbow.y).toBeCloseTo(shoulder.y)
    expect(wrist.x).toBeCloseTo(elbow.x - 43)
    expect(wrist.y).toBeCloseTo(elbow.y)
    expect(after.find((joint) => joint.id === 'backHand')).toEqual(
      before.find((joint) => joint.id === 'backHand')
    )
  })

  it.each(['bind', 'idle', 'walk', 'punch'] as RigClip[])(
    '%s preserves attachment distances throughout the cycle',
    (clip) => {
      for (const phase of [0, 0.13, 0.25, 0.42, 0.75, 1]) {
        const joints = resolveRig(clip, phase)
        for (const joint of joints) {
          expect(Number.isFinite(joint.x + joint.y + joint.angle)).toBe(true)
          expect(Math.hypot(joint.tip[0] - joint.x, joint.tip[1] - joint.y)).toBeCloseTo(
            Math.hypot(...joint.end)
          )
          const parent = joints.find((candidate) => candidate.id === joint.parent)
          if (parent)
            expect(Math.hypot(joint.x - parent.x, joint.y - parent.y)).toBeCloseTo(
              Math.hypot(...joint.offset)
            )
        }
      }
    }
  )

  it('extends the punching hand and recovers to the starting pose', () => {
    const hand = (phase: number) =>
      resolveRig('punch', phase).find((joint) => joint.id === 'frontHand')!
    expect(hand(0.42).x).toBeGreaterThan(hand(0).x + 60)
    expect(hand(1).x).toBeCloseTo(hand(0).x)
    expect(hand(1).y).toBeCloseTo(hand(0).y)
  })

  it.each(['idle', 'walk', 'punch'] as RigClip[])(
    '%s closes its loop without an angle or root-position jump',
    (clip) => {
      const first = sampleRigClip(clip, 0)
      const last = sampleRigClip(clip, 1)
      expect(last.x).toBeCloseTo(first.x)
      expect(last.y).toBeCloseTo(first.y)
      for (const bone of RIG_BONES)
        expect(last.angles[bone.id] ?? 0).toBeCloseTo(first.angles[bone.id] ?? 0)
    }
  )
})
