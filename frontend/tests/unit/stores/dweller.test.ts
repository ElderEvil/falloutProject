import { beforeEach, describe, expect, it } from 'vitest'
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

    store.filter.isLoading = true
    store.death.deadLoadingCount = 1

    expect(store.filter.isLoading).toBe(true)
    expect(store.death.isDeadLoading).toBe(true)
    expect('isLoading' in store.generation).toBe(false)
  })

  it('supports Pinia patches on every stateful slice', () => {
    const store = useDwellerStore()

    store.filter.$patch({ isLoading: true })
    store.death.$patch({ deadLoadingCount: 2 })

    expect(store.filter.isLoading).toBe(true)
    expect(store.death.isDeadLoading).toBe(true)
  })

  it('returns reactive refs from the filter slice', () => {
    const store = useDwellerStore()
    const { dwellers } = storeToRefs(store.filter)

    store.filter.dwellers = [{ id: 'dweller-1' }] as never

    expect(dwellers.value).toHaveLength(1)
    expect(dwellers.value[0]?.id).toBe('dweller-1')
  })

  it('keeps filter preferences on the filter slice', () => {
    const { filter } = useDwellerStore()

    filter.setFilterStatus('working')
    filter.setSortDirection('desc')

    expect(filter.filterStatus).toBe('working')
    expect(filter.sortDirection).toBe('desc')
  })

  it('keeps age-group preferences on the filter slice', () => {
    const { filter } = useDwellerStore()

    filter.setFilterAgeGroup('adult')

    expect(filter.filterAgeGroup).toBe('adult')
  })

  it('keeps sort-field preferences on the filter slice', () => {
    const { filter } = useDwellerStore()

    filter.setSortBy('happiness')

    expect(filter.sortBy).toBe('happiness')
  })

  it('keeps the list and grid display preference on the filter slice', () => {
    const { filter } = useDwellerStore()

    filter.setViewMode('grid')

    expect(filter.viewMode).toBe('grid')
  })

  it('returns null for an unknown dweller status', () => {
    const { filter } = useDwellerStore()

    expect(filter.getDwellerStatus('missing')).toBeNull()
  })

  it('starts with an empty detailed-dweller cache', () => {
    const { filter } = useDwellerStore()

    expect(filter.detailedDwellers).toEqual({})
  })

  it('starts with no revivable dwellers', () => {
    const { death } = useDwellerStore()

    expect(death.deadDwellers).toEqual([])
  })

  it('starts with no graveyard dwellers', () => {
    const { death } = useDwellerStore()

    expect(death.graveyardDwellers).toEqual([])
  })

  it('starts death loading as false', () => {
    const { death } = useDwellerStore()

    expect(death.isDeadLoading).toBe(false)
  })
})
