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

    const dx = event.clientX - dragStartX
    const dy = event.clientY - dragStartY

    // Convert pixel delta to SVG units
    const viewSize = MAP_SIZE / zoom.value
    const svgDx = (dx / svgRect.width) * viewSize
    const svgDy = (dy / svgRect.height) * viewSize

    const result = clampPan(dragStartPanX - svgDx, dragStartPanY - svgDy, zoom.value)
    panX.value = result.panX
    panY.value = result.panY
  }

  /**
   * End a drag operation. Call on mouseup.
   */
  function onDragEnd(): void {
    isDragging.value = false
  }

  return {
    // State
    zoom,
    panX,
    panY,
    isDragging,
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
  }
}
