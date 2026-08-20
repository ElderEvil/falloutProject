import { computed, onMounted, ref, watch, type ComputedRef } from 'vue'
import { useDwellerStore } from '../stores/dweller'
import type { LineageMember, LineageResponse } from '../services/lineageService'

export type LineageAction = (dwellerId: string) => void

/**
 * Loads a dweller's family lineage from the management store, exposing the
 * reactive result plus error/retry state and helpers for rendering members.
 */
export function useLineage(dwellerId: () => string | undefined, onSelect: LineageAction) {
  const { management: dwellerManagementStore } = useDwellerStore()

  const lineage: ComputedRef<LineageResponse | null> = computed(
    () => dwellerManagementStore.lineage
  )
  const isLoading = computed(() => dwellerManagementStore.isLoadingLineage)
  const error = ref<string | null>(null)

  async function load() {
    const id = dwellerId()
    if (!id) return
    error.value = null
    const result = await dwellerManagementStore.fetchLineage(id)
    if (!result) error.value = 'Failed to load family lineage.'
  }

  onMounted(load)
  watch(dwellerId, load)

  function select(member: LineageMember) {
    onSelect(member.id)
  }

  return {
    lineage,
    isLoading,
    error,
    load,
    select,
  }
}
