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

  it('puts the dweller left leg behind the right leg', () => {
    const joints = resolveRig('bind', 0)
    const back = joints.find((joint) => joint.id === 'backThigh')!
    const front = joints.find((joint) => joint.id === 'frontThigh')!
    expect(back.x).toBeGreaterThan(front.x)
    expect(back.layer).toBeLessThan(front.layer)
  })

  it('flexes each elbow during walking instead of swinging a rigid arm', () => {
    const poses = [0, 0.25, 0.5, 0.75, 1].map((phase) => sampleRigClip('walk', phase).angles)
    for (const elbow of ['frontForearm', 'backForearm'] as const) {
      const angles = poses.map((pose) => pose[elbow]!)
      expect(Math.max(...angles) - Math.min(...angles)).toBeGreaterThan(25)
      expect(Math.min(...angles.map(Math.abs))).toBeGreaterThanOrEqual(15)
    }
    expect(poses[1]!.frontForearm).toBeLessThan(poses[1]!.backForearm!)
    expect(poses[3]!.backForearm).toBeLessThan(poses[3]!.frontForearm!)
  })

  it('fits the original hip connector beneath the torso without an oversized round pelvis', () => {
    const hips = RIG_BONES.find((bone) => bone.id === 'pelvis')!.sprite.frame
    const torso = RIG_BONES.find((bone) => bone.id === 'spine')!.sprite.frame
    expect(hips[3] / hips[2]).toBeLessThan(0.55)
    expect(hips[2] / torso[2]).toBeGreaterThan(0.75)
    expect(hips[2]).toBeLessThan(torso[2] * 1.15)
  })

  it('preserves the source aspect ratio of every limb, hand and shoe', () => {
    for (const bone of RIG_BONES.filter((bone) => /Arm|Hand|Thigh|Shin|Foot/.test(bone.id))) {
      const { crop, frame } = bone.sprite
      expect(frame[2] / crop[2], bone.id).toBeCloseTo(frame[3] / crop[3], 4)
    }
  })

  it('maps the bind joints to the original Chet stance', () => {
    const joints = resolveRig('bind', 0)
    // Original 136 × 287 Chet sprite, uniformly scaled 1.25 and aligned at the neck.
    const anchors = {
      frontUpperArm: [41, 106],
      backUpperArm: [101, 105],
      frontForearm: [21, 143],
      backForearm: [113, 150],
      frontHand: [20, 182],
      backHand: [122, 178],
      frontThigh: [53, 177],
      backThigh: [84, 178],
      frontShin: [81, 224],
      backShin: [43, 218],
      frontFoot: [79, 268],
      backFoot: [30, 254],
    }
    for (const [id, point] of Object.entries(anchors)) {
      const joint = joints.find((joint) => joint.id === id)!
      expect(
        Math.hypot(joint.x - (107.5 + point[0]! * 1.25), joint.y - (90.25 + point[1]! * 1.25)),
        id
      ).toBeLessThan(0.001)
    }
  })

  it('rotates the elbow and wrist with their shoulder, leaving the opposite arm intact', () => {
    const before = resolveRig('bind', 0)
    const after = resolveRig('bind', 0, { frontUpperArm: 90 })
    const shoulder = after.find((joint) => joint.id === 'frontUpperArm')!
    const elbow = after.find((joint) => joint.id === 'frontForearm')!
    const wrist = after.find((joint) => joint.id === 'frontHand')!
    for (const child of [elbow, wrist]) {
      const original = before.find((joint) => joint.id === child.id)!
      expect(child.x).toBeCloseTo(shoulder.x - (original.y - shoulder.y))
      expect(child.y).toBeCloseTo(shoulder.y + (original.x - shoulder.x))
    }
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
