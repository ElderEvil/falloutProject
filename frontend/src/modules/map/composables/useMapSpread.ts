import { computed, type Ref } from 'vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'
import { spreadMarkers } from '../utils/spreadMarkers'

export function useMapSpread(
  locations: Ref<WastelandLocationWithDwellers[]>,
  vaultMarkers: Ref<VaultMarkerRead[]>
) {
  const spreadMap = computed(() =>
    spreadMarkers(
      [
        ...locations.value.map((loc) => ({ id: `loc-${loc.id}`, x: loc.coord_x, y: loc.coord_y })),
        ...vaultMarkers.value.map((vm, idx) => ({
          id: `vault-${idx}`,
          x: vm.coord_x,
          y: vm.coord_y,
        })),
      ],
      { collisionRadius: 7.2, maxDisplace: 4.0, iterations: 5 }
    )
  )

  function getSpread(id: string, fallbackX: number, fallbackY: number) {
    return spreadMap.value.get(id) ?? { renderX: fallbackX, renderY: fallbackY }
  }

  return { spreadMap, getSpread }
}
