import { ref, computed } from 'vue'

// ── Constants ──────────────────────────────────────────────────────────
export const MIN_ZOOM = 1
export const MAX_ZOOM = 4
export const WHEEL_STEP = 0.12
export const MAP_SIZE = 160

// ── Pure functions (unit-testable) ─────────────────────────────────────

/**
 * Clamp pan values so the visible viewBox stays within the 0..160 map bounds.
 * At zoom=1 the viewBox covers the entire map, so pan must be 0,0.
 */
export function clampPan(panX: number, panY: number, zoom: number): { panX: number; panY: number } {
  const viewSize = MAP_SIZE / zoom
  const maxPan = MAP_SIZE - viewSize
  return {
    panX: Math.max(0, Math.min(maxPan, panX)),
    panY: Math.max(0, Math.min(maxPan, panY)),
  }
}

/**
 * Compute the SVG viewBox string for the given zoom and pan.
 */
export function computeViewBox(zoom: number, panX: number, panY: number): string {
  const viewSize = MAP_SIZE / zoom
  return `${panX} ${panY} ${viewSize} ${viewSize}`
}

/**
 * Compute pan values that center the map on a target SVG coordinate
 * at the given zoom level.
 */
export function computeFocusPan(
  targetX: number,
  targetY: number,
  zoom: number
): { panX: number; panY: number } {
  const viewSize = MAP_SIZE / zoom
  return clampPan(targetX - viewSize / 2, targetY - viewSize / 2, zoom)
}

/**
 * Clamp zoom to the allowed range.
 */
export function clampZoom(zoom: number): number {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom))
}

/**
 * Compute zoom-at-point: apply a zoom delta while keeping the SVG point
 * under (mouseFracX, mouseFracY) [0..1 fraction of SVG element] fixed.
 *
 * Returns new zoom and pan values.
 */
export function computeZoomAtPoint(
  currentZoom: number,
  newZoom: number,
  mouseFracX: number,
  mouseFracY: number,
  panX: number,
  panY: number
): { zoom: number; panX: number; panY: number } {
  const clampedZoom = clampZoom(newZoom)
  if (clampedZoom === currentZoom) {
    return { zoom: currentZoom, panX, panY }
  }

  const currentViewSize = MAP_SIZE / currentZoom
  // SVG coordinate under the cursor
  const svgX = panX + mouseFracX * currentViewSize
  const svgY = panY + mouseFracY * currentViewSize

  const newViewSize = MAP_SIZE / clampedZoom
  // Keep the same SVG point at the same fractional position
  const newPan = clampPan(
    svgX - mouseFracX * newViewSize,
    svgY - mouseFracY * newViewSize,
    clampedZoom
  )

  return { zoom: clampedZoom, panX: newPan.panX, panY: newPan.panY }
}

/**
 * Compute pinch-to-zoom: apply a distance-ratio zoom anchored at the
 * pinch-start midpoint, then shift pan so the map tracks midpoint movement
 * (two-finger pan). All midpoint fractions are [0..1] of the SVG element.
 *
 * Returns new zoom and pan values.
 */
export function computePinchPan(
  startZoom: number,
  startPanX: number,
  startPanY: number,
  startDist: number,
  curDist: number,
  startMidFracX: number,
  startMidFracY: number,
  curMidFracX: number,
  curMidFracY: number
): { zoom: number; panX: number; panY: number } {
  if (startDist <= 0) {
    return { zoom: startZoom, panX: startPanX, panY: startPanY }
  }

  const newZoom = clampZoom(startZoom * (curDist / startDist))
  const base = computeZoomAtPoint(
    startZoom,
    newZoom,
    startMidFracX,
    startMidFracY,
    startPanX,
    startPanY
  )

  // Track midpoint movement: midpoint drifting right pulls the map right (pan decreases)
  const newViewSize = MAP_SIZE / base.zoom
  const shifted = clampPan(
    base.panX - (curMidFracX - startMidFracX) * newViewSize,
    base.panY - (curMidFracY - startMidFracY) * newViewSize,
    base.zoom
  )

  return { zoom: base.zoom, panX: shifted.panX, panY: shifted.panY }
}

// ── Composable ─────────────────────────────────────────────────────────

export function useMapZoomPan() {
  const zoom = ref(MIN_ZOOM)
  const panX = ref(0)
  const panY = ref(0)

  // Drag state
  const isDragging = ref(false)
  let dragStartX = 0
  let dragStartY = 0
  let dragStartPanX = 0
  let dragStartPanY = 0

  // Pinch state
  const isPinching = ref(false)
  let pinchStartDist = 0
  let pinchStartZoom = MIN_ZOOM
  let pinchStartPanX = 0
  let pinchStartPanY = 0
  let pinchStartMidX = 0.5
  let pinchStartMidY = 0.5

  const viewBox = computed(() => computeViewBox(zoom.value, panX.value, panY.value))
  const isZoomed = computed(() => zoom.value > MIN_ZOOM)

  function zoomIn(): void {
    const newZoom = clampZoom(zoom.value + WHEEL_STEP * 2)
    const centerFrac = 0.5
    const result = computeZoomAtPoint(
      zoom.value,
      newZoom,
      centerFrac,
      centerFrac,
      panX.value,
      panY.value
    )
    zoom.value = result.zoom
    panX.value = result.panX
    panY.value = result.panY
  }

  function zoomOut(): void {
    const newZoom = clampZoom(zoom.value - WHEEL_STEP * 2)
    const centerFrac = 0.5
    const result = computeZoomAtPoint(
      zoom.value,
      newZoom,
      centerFrac,
      centerFrac,
      panX.value,
      panY.value
    )
    zoom.value = result.zoom
    panX.value = result.panX
    panY.value = result.panY
  }

  function resetZoom(): void {
    zoom.value = MIN_ZOOM
    panX.value = 0
    panY.value = 0
  }

  function focusOnMarker(x: number, y: number): void {
    // Zoom to at least 2x for focus
    const targetZoom = Math.max(zoom.value, 2)
    zoom.value = targetZoom
    const result = computeFocusPan(x, y, targetZoom)
    panX.value = result.panX
    panY.value = result.panY
  }

  /**
   * Wheel handler — call with the mouse event and the SVG element's bounding rect.
   * Returns true if the event was consumed (zoom changed).
   */
  function onWheel(event: WheelEvent, svgRect: DOMRect): boolean {
    const fracX = (event.clientX - svgRect.left) / svgRect.width
    const fracY = (event.clientY - svgRect.top) / svgRect.height

    // Clamp fractions to [0, 1]
    const mx = Math.max(0, Math.min(1, fracX))
    const my = Math.max(0, Math.min(1, fracY))

    const direction = event.deltaY < 0 ? 1 : -1
    const newZoom = clampZoom(zoom.value + direction * WHEEL_STEP)

    const result = computeZoomAtPoint(zoom.value, newZoom, mx, my, panX.value, panY.value)
    const changed =
      result.zoom !== zoom.value || result.panX !== panX.value || result.panY !== panY.value

    zoom.value = result.zoom
    panX.value = result.panX
    panY.value = result.panY

    return changed
  }

  function applyDragMove(clientX: number, clientY: number, svgRect: DOMRect): void {
    const dx = clientX - dragStartX
    const dy = clientY - dragStartY

    // Convert pixel delta to SVG units
    const viewSize = MAP_SIZE / zoom.value
    const svgDx = (dx / svgRect.width) * viewSize
    const svgDy = (dy / svgRect.height) * viewSize

    const result = clampPan(dragStartPanX - svgDx, dragStartPanY - svgDy, zoom.value)
    panX.value = result.panX
    panY.value = result.panY
  }

  function touchDistance(t1: Touch, t2: Touch): number {
    return Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY)
  }

  function touchMidFraction(
    t1: Touch,
    t2: Touch,
    svgRect: DOMRect
  ): { mx: number; my: number } {
    const midX = (t1.clientX + t2.clientX) / 2
    const midY = (t1.clientY + t2.clientY) / 2
    return {
      mx: Math.max(0, Math.min(1, (midX - svgRect.left) / svgRect.width)),
      my: Math.max(0, Math.min(1, (midY - svgRect.top) / svgRect.height)),
    }
  }

  /**
   * Start a drag operation. Call on mousedown.
   */
  function onDragStart(event: MouseEvent, _svgRect: DOMRect): void {
    if (zoom.value <= MIN_ZOOM) return
    isDragging.value = true
    dragStartX = event.clientX
    dragStartY = event.clientY
    dragStartPanX = panX.value
    dragStartPanY = panY.value
  }

  /**
   * Continue a drag operation. Call on mousemove.
   */
  function onDragMove(event: MouseEvent, svgRect: DOMRect): void {
    if (!isDragging.value) return
    applyDragMove(event.clientX, event.clientY, svgRect)
  }

  /**
   * End a drag operation. Call on mouseup.
   */
  function onDragEnd(): void {
    isDragging.value = false
  }

  /**
   * Touch start: single finger begins a pan drag (when zoomed), two fingers
   * begin a pinch. The map container uses `touch-action: none` CSS so no
   * preventDefault is needed here.
   */
  function onTouchStart(event: TouchEvent, svgRect: DOMRect): void {
    const touches = event.touches
    if (touches.length === 1 && touches[0]) {
      if (zoom.value <= MIN_ZOOM) {
        isDragging.value = false
        return
      }
      isPinching.value = false
      isDragging.value = true
      dragStartX = touches[0].clientX
      dragStartY = touches[0].clientY
      dragStartPanX = panX.value
      dragStartPanY = panY.value
    } else if (touches.length >= 2 && touches[0] && touches[1]) {
      isDragging.value = false
      isPinching.value = true
      pinchStartDist = touchDistance(touches[0], touches[1])
      pinchStartZoom = zoom.value
      pinchStartPanX = panX.value
      pinchStartPanY = panY.value
      const mid = touchMidFraction(touches[0], touches[1], svgRect)
      pinchStartMidX = mid.mx
      pinchStartMidY = mid.my
    }
  }

  /**
   * Touch move: drive an active pinch (zoom + two-finger pan) or an active
   * single-finger pan drag.
   */
  function onTouchMove(event: TouchEvent, svgRect: DOMRect): void {
    const touches = event.touches
    if (isPinching.value && touches.length >= 2 && touches[0] && touches[1]) {
      const curDist = touchDistance(touches[0], touches[1])
      const curMid = touchMidFraction(touches[0], touches[1], svgRect)
      const result = computePinchPan(
        pinchStartZoom,
        pinchStartPanX,
        pinchStartPanY,
        pinchStartDist,
        curDist,
        pinchStartMidX,
        pinchStartMidY,
        curMid.mx,
        curMid.my
      )
      zoom.value = result.zoom
      panX.value = result.panX
      panY.value = result.panY
      return
    }
    if (isDragging.value && touches.length === 1 && touches[0]) {
      applyDragMove(touches[0].clientX, touches[0].clientY, svgRect)
    }
  }

  /**
   * Touch end: clear pinch state; when lifting one finger of a pinch, the
   * remaining finger seamlessly continues as a pan drag from its position.
   */
  function onTouchEnd(event: TouchEvent): void {
    const remaining = event.touches.length
    if (remaining < 2) isPinching.value = false
    if (remaining === 0) {
      isDragging.value = false
    } else if (remaining === 1 && event.touches[0]) {
      if (zoom.value > MIN_ZOOM) {
        isDragging.value = true
        dragStartX = event.touches[0].clientX
        dragStartY = event.touches[0].clientY
        dragStartPanX = panX.value
        dragStartPanY = panY.value
      } else {
        isDragging.value = false
      }
    }
  }

  return {
    // State
    zoom,
    panX,
    panY,
    isDragging,
    isPinching,
    // Computed
    viewBox,
    isZoomed,
    // Actions
    zoomIn,
    zoomOut,
    resetZoom,
    focusOnMarker,
    // Event handlers
    onWheel,
    onDragStart,
    onDragMove,
    onDragEnd,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
  }
}
