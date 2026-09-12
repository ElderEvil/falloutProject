import { ref, type ComputedRef, type Ref } from 'vue'
import type {
  MarkerClickPayload,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
} from '../models/map'
import type { SpreadResult } from '../utils/spreadMarkers'

export function useMarkerSelection(
  vaultMarkers: Ref<VaultMarkerRead[]>,
  spreadMap: ComputedRef<Map<string, SpreadResult>>,
  focusOnMarker: (x: number, y: number) => void,
  emit: (event: 'marker-click', payload: MarkerClickPayload) => void
) {
  const selectedMarkerId = ref<string | null>(null)
  const hasDragMoved = ref(false)

  function markerId(payload: MarkerClickPayload): string {
    return payload.kind === 'location'
      ? `loc-${payload.data.id}`
      : `vault-${vaultMarkers.value.indexOf(payload.data)}`
  }

  function onLocationClick(loc: WastelandLocationWithDwellers) {
    if (hasDragMoved.value) return
    selectedMarkerId.value = `loc-${loc.id}`
    emit('marker-click', { kind: 'location', data: loc })
  }

  function onVaultClick(marker: VaultMarkerRead) {
    if (hasDragMoved.value) return
    selectedMarkerId.value = `vault-${vaultMarkers.value.indexOf(marker)}`
    emit('marker-click', { kind: 'vault', data: marker })
  }

  function onPanelMarkerSelect(payload: MarkerClickPayload) {
    const id = markerId(payload)
    const pos = spreadMap.value.get(id)
    focusOnMarker(pos?.renderX ?? payload.data.coord_x, pos?.renderY ?? payload.data.coord_y)
    selectedMarkerId.value = id
    emit('marker-click', payload)
  }

  return { selectedMarkerId, hasDragMoved, onLocationClick, onVaultClick, onPanelMarkerSelect }
}
