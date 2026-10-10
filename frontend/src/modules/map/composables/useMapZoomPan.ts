import { ref, computed } from 'vue'

// ── Constants ──────────────────────────────────────────────────────────
export const MIN_ZOOM = 1
export const MAX_ZOOM = 5
export const WHEEL_STEP = 0.12
export const MAP_SIZE = 160

// ── Pure functions (unit-testable) ─────────────────────────────────────

/**
 * The map fills a full-bleed rectangular screen with a cover ("slice") fit, so
 * the visible SVG window is the viewBox on one axis and cropped on the other.
 * `aspect` is viewport width / height; a square viewport (0, missing or
 * non-finite input) preserves the historical square-pane behaviour.
 */
function normalizedAspect(aspect: number): number {
  return Number.isFinite(aspect) && aspect > 0 ? aspect : 1
}

/** Visible SVG span per axis for the cover fit at this zoom. */
export function visibleSpan(zoom: number, aspect = 1): { x: number; y: number } {
  const viewSize = MAP_SIZE / zoom
  const ratio = normalizedAspect(aspect)
  return { x: viewSize * Math.min(1, ratio), y: viewSize * Math.min(1, 1 / ratio) }
}

/**
 * Whether any pan is possible at this zoom: true once the visible window is
 * smaller than the world on either axis — including zoom=1 on a full-bleed
 * viewport whose cover fit crops one axis.
 */
export function canPanAt(zoom: number, aspect = 1): boolean {
  const span = visibleSpan(zoom, aspect)
  return span.x < MAP_SIZE || span.y < MAP_SIZE
}

/**
 * Clamp pan values so the visible window stays within the 0..160 map bounds.
 * The viewBox centre is pinned to the viewport centre, so the visible window
 * sits centred on the viewBox. With a square viewport this is the historical
 * behaviour: at zoom=1 the window covers the entire map, so pan must be 0,0.
 */
export function clampPan(
  panX: number,
  panY: number,
  zoom: number,
  aspect = 1
): { panX: number; panY: number } {
  const viewSize = MAP_SIZE / zoom
  const span = visibleSpan(zoom, aspect)
  const minX = (span.x - viewSize) / 2
  const maxX = MAP_SIZE - (viewSize + span.x) / 2
  const minY = (span.y - viewSize) / 2
  const maxY = MAP_SIZE - (viewSize + span.y) / 2
  return {
    panX: Math.max(minX, Math.min(maxX, panX)),
    panY: Math.max(minY, Math.min(maxY, panY)),
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
  zoom: number,
  aspect = 1
): { panX: number; panY: number } {
  const viewSize = MAP_SIZE / zoom
  return clampPan(targetX - viewSize / 2, targetY - viewSize / 2, zoom, aspect)
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
  panY: number,
  aspect = 1
): { zoom: number; panX: number; panY: number } {
  const clampedZoom = clampZoom(newZoom)
  if (clampedZoom === currentZoom) {
    return { zoom: currentZoom, panX, panY }
  }

  const currentViewSize = MAP_SIZE / currentZoom
  const currentSpan = visibleSpan(currentZoom, aspect)
  // SVG coordinate under the cursor within the visibly cropped window
  const svgX = panX + (currentViewSize - currentSpan.x) / 2 + mouseFracX * currentSpan.x
  const svgY = panY + (currentViewSize - currentSpan.y) / 2 + mouseFracY * currentSpan.y

  const newViewSize = MAP_SIZE / clampedZoom
  const newSpan = visibleSpan(clampedZoom, aspect)
  // Keep the same SVG point at the same fractional position
  const newPan = clampPan(
    svgX - mouseFracX * newSpan.x - (newViewSize - newSpan.x) / 2,
    svgY - mouseFracY * newSpan.y - (newViewSize - newSpan.y) / 2,
    clampedZoom,
    aspect
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
  curMidFracY: number,
  aspect = 1
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
    startPanY,
    aspect
  )

  // Track midpoint movement: midpoint drifting right pulls the map right (pan decreases)
  const newSpan = visibleSpan(base.zoom, aspect)
  const shifted = clampPan(
    base.panX - (curMidFracX - startMidFracX) * newSpan.x,
    base.panY - (curMidFracY - startMidFracY) * newSpan.y,
    base.zoom,
    aspect
  )

  return { zoom: base.zoom, panX: shifted.panX, panY: shifted.panY }
}

// ── Composable ─────────────────────────────────────────────────────────

export function useMapZoomPan() {
  const zoom = ref(MIN_ZOOM)
  const panX = ref(0)
  const panY = ref(0)
  const viewportAspect = ref(1)

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
  const isPanned = computed(() => panX.value !== 0 || panY.value !== 0)
  const canPan = computed(() => canPanAt(zoom.value, viewportAspect.value))

  /**
   * Record the rendered viewport shape so the cover-fit pan bounds and
   * zoom-at-point math know which axis is cropped. Call on resize.
   */
  function syncViewport(svgRect: DOMRect): void {
    viewportAspect.value = svgRect.height > 0 ? svgRect.width / svgRect.height : 1
    const bounded = clampPan(panX.value, panY.value, zoom.value, viewportAspect.value)
    panX.value = bounded.panX
    panY.value = bounded.panY
  }

  function zoomIn(): void {
    const newZoom = clampZoom(zoom.value + WHEEL_STEP * 2)
    const centerFrac = 0.5
    const result = computeZoomAtPoint(
      zoom.value,
      newZoom,
      centerFrac,
      centerFrac,
      panX.value,
      panY.value,
      viewportAspect.value
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
      panY.value,
      viewportAspect.value
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

  function focusOnMarker(x: number, y: number, minZoom = 2): void {
    // Zoom to at least 2x for focus
    const targetZoom = clampZoom(Math.max(zoom.value, minZoom))
    zoom.value = targetZoom
    const result = computeFocusPan(x, y, targetZoom, viewportAspect.value)
    panX.value = result.panX
    panY.value = result.panY
  }

  /**
   * Wheel handler — call with the mouse event and the SVG element's bounding rect.
   * Returns true if the event was consumed (zoom changed).
   */
  function onWheel(event: WheelEvent, svgRect: DOMRect): boolean {
    syncViewport(svgRect)
    const fracX = (event.clientX - svgRect.left) / svgRect.width
    const fracY = (event.clientY - svgRect.top) / svgRect.height

    // Clamp fractions to [0, 1]
    const mx = Math.max(0, Math.min(1, fracX))
    const my = Math.max(0, Math.min(1, fracY))

    const direction = event.deltaY < 0 ? 1 : -1
    const newZoom = clampZoom(zoom.value + direction * WHEEL_STEP)

    const result = computeZoomAtPoint(
      zoom.value,
      newZoom,
      mx,
      my,
      panX.value,
      panY.value,
      viewportAspect.value
    )
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

    // The square viewBox is cover-fitted, so one pixel is the same number of
    // SVG units on both axes: the longest edge drives the scale.
    const viewSize = MAP_SIZE / zoom.value
    const scale = Math.max(svgRect.width, svgRect.height) / viewSize
    if (scale <= 0) return
    const svgDx = dx / scale
    const svgDy = dy / scale

    const result = clampPan(
      dragStartPanX - svgDx,
      dragStartPanY - svgDy,
      zoom.value,
      viewportAspect.value
    )
    panX.value = result.panX
    panY.value = result.panY
  }

  function touchDistance(t1: Touch, t2: Touch): number {
    return Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY)
  }

  function touchMidFraction(t1: Touch, t2: Touch, svgRect: DOMRect): { mx: number; my: number } {
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
  function onDragStart(event: MouseEvent, svgRect: DOMRect): void {
    syncViewport(svgRect)
    if (!canPan.value) return
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
   * Touch start: single finger begins a pan drag (whenever the cover fit
   * leaves anything to pan), two fingers begin a pinch. The map container uses
   * `touch-action: none` CSS so no preventDefault is needed here.
   */
  function onTouchStart(event: TouchEvent, svgRect: DOMRect): void {
    syncViewport(svgRect)
    const touches = event.touches
    if (touches.length === 1 && touches[0]) {
      if (!canPan.value) {
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
        curMid.my,
        viewportAspect.value
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
      if (canPan.value) {
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
    viewportAspect,
    // Computed
    viewBox,
    isZoomed,
    isPanned,
    canPan,
    // Actions
    zoomIn,
    zoomOut,
    resetZoom,
    focusOnMarker,
    syncViewport,
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
