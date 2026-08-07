import { describe, it, expect } from 'vitest'
import {
  clampPan,
  clampZoom,
  computeViewBox,
  computeFocusPan,
  computeZoomAtPoint,
  MIN_ZOOM,
  MAX_ZOOM,
} from '@/modules/map/composables/useMapZoomPan'

describe('useMapZoomPan — pure functions', () => {
  describe('clampPan', () => {
    it('should return 0,0 at zoom=1 regardless of input', () => {
      const result = clampPan(50, 50, 1)
      expect(result.panX).toBe(0)
      expect(result.panY).toBe(0)
    })

    it('should clamp pan so viewBox stays within 0..160 bounds', () => {
      const zoom = 2 // viewSize = 80, maxPan = 80
      const result = clampPan(90, -10, zoom)
      expect(result.panX).toBe(80) // clamped to maxPan
      expect(result.panY).toBe(0) // clamped to 0
    })

    it('should allow valid pan values through unchanged', () => {
      const zoom = 2
      const result = clampPan(25, 30, zoom)
      expect(result.panX).toBe(25)
      expect(result.panY).toBe(30)
    })

    it('should handle maximum zoom (4x) correctly', () => {
      const zoom = 4 // viewSize = 40, maxPan = 120
      const result = clampPan(150, 150, zoom)
      expect(result.panX).toBe(120)
      expect(result.panY).toBe(120)
    })
  })

  describe('clampZoom', () => {
    it('should clamp zoom below MIN_ZOOM to MIN_ZOOM', () => {
      expect(clampZoom(0.5)).toBe(MIN_ZOOM)
    })

    it('should clamp zoom above MAX_ZOOM to MAX_ZOOM', () => {
      expect(clampZoom(10)).toBe(MAX_ZOOM)
    })

    it('should pass through valid zoom values', () => {
      expect(clampZoom(2)).toBe(2)
      expect(clampZoom(3.5)).toBe(3.5)
    })
  })

  describe('computeViewBox', () => {
    it('should return "0 0 160 160" at zoom=1 and no pan', () => {
      expect(computeViewBox(1, 0, 0)).toBe('0 0 160 160')
    })

    it('should halve viewBox dimensions at zoom=2', () => {
      expect(computeViewBox(2, 0, 0)).toBe('0 0 80 80')
    })

    it('should offset by pan values', () => {
      expect(computeViewBox(2, 10, 20)).toBe('10 20 80 80')
    })
  })

  describe('computeFocusPan', () => {
    it('should center on the target at zoom=2 (viewSize=80)', () => {
      const result = computeFocusPan(75, 75, 2)
      // pan = 75 - 80/2 = 35, maxPan = 80
      expect(result.panX).toBe(35)
      expect(result.panY).toBe(35)
    })

    it('should return 0,0 at zoom=1 (full map always centered)', () => {
      const result = computeFocusPan(50, 50, 1)
      expect(result.panX).toBe(0)
      expect(result.panY).toBe(0)
    })

    it('should clamp when target is near edge', () => {
      const result = computeFocusPan(5, 5, 4) // viewSize=25
      // pan = 5 - 12.5 = -7.5, clamped to 0
      expect(result.panX).toBe(0)
      expect(result.panY).toBe(0)
    })

    it('should center on a mid-map target at high zoom', () => {
      const result = computeFocusPan(50, 50, 4) // viewSize=40
      // pan = 50 - 20 = 30, maxPan = 120
      expect(result.panX).toBe(30)
      expect(result.panY).toBe(30)
    })
  })

  describe('computeZoomAtPoint', () => {
    it('should return same state if clamped zoom equals current', () => {
      const result = computeZoomAtPoint(1, 0.5, 0.5, 0.5, 0, 0)
      expect(result.zoom).toBe(1)
      expect(result.panX).toBe(0)
      expect(result.panY).toBe(0)
    })

    it('should keep the center point fixed when zooming from center', () => {
      // At zoom=1, center (0.5, 0.5) maps to SVG (80, 80) on 160 map
      const result = computeZoomAtPoint(1, 2, 0.5, 0.5, 0, 0)
      expect(result.zoom).toBe(2)
      // New viewSize = 80, pan should center on (80, 80) → panX = 80 - 0.5*80 = 40
      expect(result.panX).toBe(40)
      expect(result.panY).toBe(40)
    })

    it('should clamp the resulting pan to valid bounds', () => {
      // Zoom in at top-left corner
      const result = computeZoomAtPoint(1, 4, 0, 0, 0, 0)
      expect(result.zoom).toBe(4)
      expect(result.panX).toBeGreaterThanOrEqual(0)
      expect(result.panY).toBeGreaterThanOrEqual(0)
    })

    it('should handle zoom-out from a panned state', () => {
      const result = computeZoomAtPoint(4, 2, 0.5, 0.5, 50, 50)
      expect(result.zoom).toBe(2)
      // viewSize at zoom=4 is 40, SVG point at center = 50 + 0.5*40 = 70
      // viewSize at zoom=2 is 80, newPan = 70 - 0.5*80 = 30
      expect(result.panX).toBe(30)
      expect(result.panY).toBe(30)
    })
  })
})
