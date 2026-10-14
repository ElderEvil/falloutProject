import { describe, expect, it } from 'vitest'
import {
  ORIENTATION_STEPS,
  type OnboardingLesson,
  type TeachingSnapshot,
} from '@/modules/progression/models/onboardingSteps'

const EMPTY_SNAPSHOT: TeachingSnapshot = {
  vault: null,
  rooms: [],
  dwellers: [],
  objectives: [],
  activeRuns: [],
  lessons: {},
}

const byId = new Map<OnboardingLesson['id'], OnboardingLesson>(
  ORIENTATION_STEPS.map((step) => [step.id, step] as const)
)

describe('onboardingSteps', () => {
  it('authors the five orientation lessons in order with stable ids', () => {
    expect(ORIENTATION_STEPS.map((step) => step.id)).toEqual([
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing',
      'orientation.departure',
    ])
  })

  it('links only the objective-backed lessons to server template keys', () => {
    expect(byId.get('orientation.resources')?.templateKey).toBeUndefined()
    expect(byId.get('orientation.generator')?.templateKey).toBeUndefined()
    expect(byId.get('orientation.staffing')?.templateKey).toBe('starter:assign a dweller correctly')
    expect(byId.get('orientation.housing')?.templateKey).toBe('starter:build a living quarters')
    expect(byId.get('orientation.departure')?.templateKey).toBe('starter:send a dweller exploring')
  })

  it('anchors each lesson to a real data-onboarding target', () => {
    expect(byId.get('orientation.resources')?.anchors).toContain('resource-power')
    expect(byId.get('orientation.generator')?.anchors).toContain('room-power')
    expect(byId.get('orientation.staffing')?.anchors).toContain('nav-dwellers')
    expect(byId.get('orientation.housing')?.anchors).toContain('build-living-room')
    expect(byId.get('orientation.departure')?.anchors).toEqual(
      expect.arrayContaining(['wasteland', 'nav-exploration'])
    )
  })

  it('keeps eligibility pure and unknown until the checks are wired', () => {
    for (const step of ORIENTATION_STEPS) {
      expect(step.eligibility(EMPTY_SNAPSHOT)).toBe('unknown')
    }
  })
})
