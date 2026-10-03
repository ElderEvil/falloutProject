import { ref, type ComputedRef, type Ref } from 'vue'
import type {
  ExpeditionSiteMarkerRead,
  MarkerClickPayload,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
} from '../models/map'
import type { SpreadResult } from '../utils/spreadMarkers'

export function useMarkerSelection(
  selectedMarkerId: Ref<string | null>,
  spreadMap: ComputedRef<Map<string, SpreadResult>>,
  focusOnMarker: (x: number, y: number) => void,
  emit: (event: 'marker-click', payload: MarkerClickPayload) => void
) {
  const hasDragMoved = ref(false)

  // Vault markers have no stable backend IDs (computed signals), so key them by
  // name, which survives replacement and reordering unlike array indexes.
  function markerId(payload: MarkerClickPayload): string {
    if (payload.kind === 'location') return `loc-${payload.data.id}`
    if (payload.kind === 'site') return `site-${payload.data.id}`
    return `vault-${payload.data.name}`
  }

  function onLocationClick(loc: WastelandLocationWithDwellers) {
    if (hasDragMoved.value) return
    selectedMarkerId.value = `loc-${loc.id}`
    emit('marker-click', { kind: 'location', data: loc })
  }

  function onVaultClick(marker: VaultMarkerRead) {
    if (hasDragMoved.value) return
    selectedMarkerId.value = `vault-${marker.name}`
    emit('marker-click', { kind: 'vault', data: marker })
  }

  function onSiteClick(site: ExpeditionSiteMarkerRead) {
    if (hasDragMoved.value) return
    selectedMarkerId.value = `site-${site.id}`
    emit('marker-click', { kind: 'site', data: site })
  }

  function onPanelMarkerSelect(payload: MarkerClickPayload) {
    const id = markerId(payload)
    const pos = spreadMap.value.get(id)
    focusOnMarker(pos?.renderX ?? payload.data.coord_x, pos?.renderY ?? payload.data.coord_y)
    selectedMarkerId.value = id
    emit('marker-click', payload)
  }

  return {
    selectedMarkerId,
    hasDragMoved,
    onLocationClick,
    onVaultClick,
    onSiteClick,
    onPanelMarkerSelect,
  }
}
