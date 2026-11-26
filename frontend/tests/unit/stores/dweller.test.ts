import { beforeEach, describe, expect, it } from 'vite-plus/test'
import { storeToRefs, createPinia, setActivePinia } from 'pinia'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

describe('Dweller store slices', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('exposes the five underlying Pinia stores by concern', () => {
    const store = useDwellerStore()
    expect(store.filter.$id).toBe('dwellerFilter')
    expect(store.generation.$id).toBe('dwellerGeneration')
    expect(store.management.$id).toBe('dwellerManagement')
    expect(store.medical.$id).toBe('dwellerMedical')
    expect(store.death.$id).toBe('dwellerDeath')
  })

  it('keeps loading state independent for filter, generation, and death work', () => {
    const store = useDwellerStore()
    store.death.deadLoadingCount = 1
    expect(store.filter.isLoading).toBe(false)
    expect(store.death.isDeadLoading).toBe(true)
    expect('isLoading' in store.generation).toBe(false)
  })

  it('supports Pinia patches on every stateful slice', () => {
    const store = useDwellerStore()
    store.filter.$patch({ dwellers: [] })
    store.death.$patch({ deadLoadingCount: 2 })
    expect(store.filter.dwellers).toEqual([])
    expect(store.death.isDeadLoading).toBe(true)
  })

  it('returns reactive refs from the filter slice', () => {
    const store = useDwellerStore()
    const { dwellers } = storeToRefs(store.filter)
    store.filter.dwellers = [{ id: 'dweller-1' }] as never
    expect(dwellers.value).toHaveLength(1)
    expect(dwellers.value[0]?.id).toBe('dweller-1')
  })

  it('keeps every view preference on the filter slice', () => {
    const { filter } = useDwellerStore()

    filter.setFilterStatus('working')
    filter.setFilterAgeGroup('adult')
    filter.setSortBy('happiness')
    filter.setSortDirection('desc')
    filter.setViewMode('grid')
    expect(filter).toMatchObject({
      filterStatus: 'working',
      filterAgeGroup: 'adult',
      sortBy: 'happiness',
      sortDirection: 'desc',
      viewMode: 'grid',
    })
  })

  it('starts with the documented empty state on both slices', () => {
    const { filter, death } = useDwellerStore()
    expect(filter.getDwellerStatus('missing')).toBeNull()
    expect(filter.detailedDwellers).toEqual({})
    expect(death.deadDwellers).toEqual([])
    expect(death.graveyardDwellers).toEqual([])
    expect(death.isDeadLoading).toBe(false)
  })
})
