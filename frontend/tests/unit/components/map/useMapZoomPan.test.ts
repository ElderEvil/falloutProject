import { describe, it, expect } from 'vitest'
import {
  clampPan,
  clampZoom,
  computeViewBox,
  computeFocusPan,
  computeZoomAtPoint,
  computePinchPan,
  canPanAt,
  useMapZoomPan,
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

  describe('cover-fit pan bounds (full-bleed viewport)', () => {
    it('reports whether panning is possible per zoom and viewport aspect', () => {
      expect(canPanAt(1, 1)).toBe(false)
      expect(canPanAt(2, 1)).toBe(true)
      expect(canPanAt(1, 2)).toBe(true)
      expect(canPanAt(1, 0.5)).toBe(true)
      expect(canPanAt(1, 0)).toBe(false)
    })

    it('clamps pan to the cropped axis at zoom=1 on a wide viewport', () => {
      // aspect 2 → the visible window is 160x80 units, so panY ranges [-40, 40].
      expect(clampPan(10, 999, 1, 2)).toEqual({ panX: 0, panY: 40 })
      expect(clampPan(10, -999, 1, 2)).toEqual({ panX: 0, panY: -40 })
    })

    it('keeps the square-viewport pan bounds unchanged', () => {
      expect(clampPan(50, 50, 1, 1)).toEqual({ panX: 0, panY: 0 })
      expect(clampPan(90, -10, 2, 1)).toEqual({ panX: 80, panY: 0 })
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

  describe('computePinchPan', () => {
    it('should double zoom when pinch distance doubles, anchored at center', () => {
      const result = computePinchPan(2, 40, 40, 100, 200, 0.5, 0.5, 0.5, 0.5)
      expect(result.zoom).toBe(4)
      expect(result.panX).toBe(60)
      expect(result.panY).toBe(60)
    })

    it('should halve zoom when pinch distance halves', () => {
      const result = computePinchPan(2, 40, 40, 200, 100, 0.5, 0.5, 0.5, 0.5)
      expect(result.zoom).toBe(1)
      expect(result.panX).toBe(0)
      expect(result.panY).toBe(0)
    })

    it('should clamp zoom at MAX_ZOOM', () => {
      const result = computePinchPan(MAX_ZOOM, 60, 60, 100, 400, 0.5, 0.5, 0.5, 0.5)
      expect(result.zoom).toBe(MAX_ZOOM)
      expect(result.panX).toBe(60)
      expect(result.panY).toBe(60)
    })

    it('should pan when the midpoint moves without zoom change', () => {
      const result = computePinchPan(2, 40, 40, 100, 100, 0.5, 0.5, 0.6, 0.5)
      expect(result.zoom).toBe(2)
      expect(result.panX).toBeCloseTo(32)
      expect(result.panY).toBe(40)
    })

    it('should return the start state when start distance is zero', () => {
      const result = computePinchPan(2, 40, 40, 0, 100, 0.5, 0.5, 0.5, 0.5)
      expect(result).toEqual({ zoom: 2, panX: 40, panY: 40 })
    })
  })

  describe('touch handlers', () => {
    const rect = { left: 0, top: 0, width: 400, height: 400 } as DOMRect

    function touchEvent(points: { x: number; y: number }[]): TouchEvent {
      return {
        touches: points.map((p) => ({ clientX: p.x, clientY: p.y })),
      } as unknown as TouchEvent
    }

    it('should pan on single-finger drag when zoomed', () => {
      const map = useMapZoomPan()
      map.focusOnMarker(80, 80)
      expect(map.zoom.value).toBe(2)

      map.onTouchStart(touchEvent([{ x: 200, y: 200 }]), rect)
      expect(map.isDragging.value).toBe(true)
      map.onTouchMove(touchEvent([{ x: 220, y: 200 }]), rect)

      // dx=20px on a 400px element at zoom=2 (viewSize=80): svgDx = 4
      expect(map.panX.value).toBe(36)
      expect(map.panY.value).toBe(40)

      map.onTouchEnd(touchEvent([]))
      expect(map.isDragging.value).toBe(false)
    })

    it('should ignore single-finger drag at zoom=1', () => {
      const map = useMapZoomPan()
      map.onTouchStart(touchEvent([{ x: 200, y: 200 }]), rect)
      expect(map.isDragging.value).toBe(false)
      map.onTouchMove(touchEvent([{ x: 250, y: 250 }]), rect)
      expect(map.panX.value).toBe(0)
      expect(map.panY.value).toBe(0)
    })

    it('should zoom on pinch-out and clear state on touch end', () => {
      const map = useMapZoomPan()
      map.focusOnMarker(80, 80)

      map.onTouchStart(
        touchEvent([
          { x: 100, y: 200 },
          { x: 300, y: 200 },
        ]),
        rect
      )
      expect(map.isPinching.value).toBe(true)

      map.onTouchMove(
        touchEvent([
          { x: 50, y: 200 },
          { x: 350, y: 200 },
        ]),
        rect
      )
      expect(map.zoom.value).toBeCloseTo(3)
      expect(map.panX.value).toBeCloseTo(160 / 3)
      expect(map.panY.value).toBeCloseTo(160 / 3)

      map.onTouchEnd(touchEvent([]))
      expect(map.isPinching.value).toBe(false)
      expect(map.isDragging.value).toBe(false)
    })

    it('should continue panning with the remaining finger after a pinch', () => {
      const map = useMapZoomPan()
      map.focusOnMarker(80, 80)
      map.onTouchStart(
        touchEvent([
          { x: 100, y: 200 },
          { x: 300, y: 200 },
        ]),
        rect
      )
      map.onTouchMove(
        touchEvent([
          { x: 50, y: 200 },
          { x: 350, y: 200 },
        ]),
        rect
      )
      const zoomAfterPinch = map.zoom.value

      map.onTouchEnd(touchEvent([{ x: 50, y: 200 }]))
      expect(map.isPinching.value).toBe(false)
      expect(map.isDragging.value).toBe(true)

      const panBefore = map.panX.value
      map.onTouchMove(touchEvent([{ x: 70, y: 200 }]), rect)
      expect(map.zoom.value).toBe(zoomAfterPinch)
      expect(map.panX.value).toBeLessThan(panBefore)
    })

    it('starts a pan drag at zoom=1 when the cover fit crops an axis', () => {
      const map = useMapZoomPan()
      const wide = { left: 0, top: 0, width: 800, height: 400 } as DOMRect
      map.syncViewport(wide)

      expect(map.canPan.value).toBe(true)
      map.onTouchStart(touchEvent([{ x: 400, y: 200 }]), wide)
      expect(map.isDragging.value).toBe(true)

      map.onTouchMove(touchEvent([{ x: 400, y: 240 }]), wide)
      // dy=40px at scale 800/160=5 → 8 SVG units; pan starts at 0.
      expect(map.panX.value).toBe(0)
      expect(map.panY.value).toBe(-8)

      map.onTouchEnd(touchEvent([]))
      expect(map.isDragging.value).toBe(false)
    })

    it('does not start a drag at zoom=1 on a square viewport', () => {
      const map = useMapZoomPan()
      map.syncViewport(rect)

      expect(map.canPan.value).toBe(false)
      map.onTouchStart(touchEvent([{ x: 200, y: 200 }]), rect)
      expect(map.isDragging.value).toBe(false)
    })
  })
})
