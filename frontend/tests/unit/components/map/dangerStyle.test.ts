import { describe, it, expect } from 'vitest'
import { riskToDangerStyle } from '@/modules/map/utils/dangerStyle'

describe('riskToDangerStyle', () => {
  it('maps a low-risk catalog entry to the low danger class', () => {
    expect(riskToDangerStyle('low')).toEqual({ level: 'low', className: 'marker-risk-low' })
  })

  it('maps a medium-risk catalog entry to the medium danger class', () => {
    expect(riskToDangerStyle('medium')).toEqual({
      level: 'medium',
      className: 'marker-risk-medium',
    })
  })

  it('maps a high-risk catalog entry to the high danger class', () => {
    expect(riskToDangerStyle('high')).toEqual({ level: 'high', className: 'marker-risk-high' })
  })

  it('maps a missing or unrecognized risk to the neutral unknown class', () => {
    const unknown = { level: 'unknown', className: 'marker-risk-unknown' }
    expect(riskToDangerStyle(undefined)).toEqual(unknown)
    expect(riskToDangerStyle(null)).toEqual(unknown)
    expect(riskToDangerStyle('')).toEqual(unknown)
    expect(riskToDangerStyle('extreme')).toEqual(unknown)
  })

  it('normalizes case and surrounding whitespace', () => {
    expect(riskToDangerStyle('  HIGH ').level).toBe('high')
    expect(riskToDangerStyle('Medium').level).toBe('medium')
  })

  it('falls back to base difficulty when the risk is unrecognized', () => {
    expect(riskToDangerStyle('', 4).level).toBe('high')
    expect(riskToDangerStyle(null, 3).level).toBe('medium')
    expect(riskToDangerStyle(null, 2).level).toBe('low')
    expect(riskToDangerStyle(null, 0).level).toBe('unknown')
    expect(riskToDangerStyle(null, null).level).toBe('unknown')
  })

  it('lets a known risk win over the difficulty band', () => {
    expect(riskToDangerStyle('low', 4).level).toBe('low')
  })
})
