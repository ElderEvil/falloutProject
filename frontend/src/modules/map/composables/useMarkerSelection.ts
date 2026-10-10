import { ref, type Ref } from 'vue'
import type {
  ExpeditionSiteMarkerRead,
  MarkerClickPayload,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
} from '../models/map'

export function useMarkerSelection(
  selectedMarkerId: Ref<string | null>,
  focusOnMarker: (x: number, y: number) => void,
  emit: (event: 'marker-click', payload: MarkerClickPayload) => void,
  isDisabled?: () => boolean
) {
  const hasDragMoved = ref(false)

  function blocked(): boolean {
    return hasDragMoved.value || (isDisabled?.() ?? false)
  }

  // Vault markers have no stable backend IDs (computed signals), so key them by
  // name, which survives replacement and reordering unlike array indexes.
  function markerId(payload: MarkerClickPayload): string {
    if (payload.kind === 'location') return `loc-${payload.data.id}`
    if (payload.kind === 'site') return `site-${payload.data.id}`
    return `vault-${payload.data.name}`
  }

  function onLocationClick(loc: WastelandLocationWithDwellers) {
    if (blocked()) return
    selectedMarkerId.value = `loc-${loc.id}`
    emit('marker-click', { kind: 'location', data: loc })
  }

  function onVaultClick(marker: VaultMarkerRead) {
    if (blocked()) return
    selectedMarkerId.value = `vault-${marker.name}`
    emit('marker-click', { kind: 'vault', data: marker })
  }

  function onSiteClick(site: ExpeditionSiteMarkerRead) {
    if (blocked()) return
    selectedMarkerId.value = `site-${site.id}`
    emit('marker-click', { kind: 'site', data: site })
  }

  function onPanelMarkerSelect(payload: MarkerClickPayload) {
    if (blocked()) return
    const id = markerId(payload)
    focusOnMarker(payload.data.coord_x, payload.data.coord_y)
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
