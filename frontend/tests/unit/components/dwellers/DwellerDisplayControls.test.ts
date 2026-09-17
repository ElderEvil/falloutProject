import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerDisplayControls from '@/modules/dwellers/components/DwellerDisplayControls.vue'
import displayControlsSource from '@/modules/dwellers/components/DwellerDisplayControls.vue?raw'
import filterPanelSource from '@/modules/dwellers/components/DwellerFilterPanel.vue?raw'
import filterGroupSource from '@/modules/dwellers/components/DwellerFilterGroup.vue?raw'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

describe('DwellerDisplayControls', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the sort control and no view toggle by default', () => {
    const wrapper = mount(DwellerDisplayControls)

    expect(wrapper.find('.display-group .select-trigger').attributes('aria-label')).toBe(
      'Sort dwellers'
    )
    expect(wrapper.find('.sort-direction-button').exists()).toBe(true)
    expect(wrapper.find('.view-toggle-btn').exists()).toBe(false)
  })

  it('updates the store when the sort option changes', async () => {
    const wrapper = mount(DwellerDisplayControls)
    const store = useDwellerStore().filter

    const sortTrigger = wrapper.find('.display-group .select-trigger')
    await sortTrigger.trigger('click')
    const levelOption = wrapper
      .findAll('.display-group .select-option')
      .find((option) => option.text().includes('Level'))
    expect(levelOption).toBeDefined()
    await levelOption!.trigger('click')

    expect(store.sortBy).toBe('level')
  })

  it('toggles the sort direction', async () => {
    const wrapper = mount(DwellerDisplayControls)
    const store = useDwellerStore().filter

    expect(store.sortDirection).toBe('asc')
    await wrapper.find('.sort-direction-button').trigger('click')

    expect(store.sortDirection).toBe('desc')
  })

  it('switches to the table view when the view toggle is shown', async () => {
    const wrapper = mount(DwellerDisplayControls, { props: { showView: true } })
    const store = useDwellerStore().filter

    const tableButton = wrapper
      .findAll('.view-toggle-btn')
      .find((btn) => btn.text().includes('Table'))
    expect(tableButton).toBeDefined()

    await tableButton!.trigger('click')

    expect(store.viewMode).toBe('table')
  })

  it('shows the column picker only in table mode and toggles a column', async () => {
    const wrapper = mount(DwellerDisplayControls, { props: { showView: true } })
    const store = useDwellerStore().filter

    expect(wrapper.find('.columns-trigger').exists()).toBe(false)

    store.setViewMode('table')
    await wrapper.vm.$nextTick()

    // The picker is collapsed behind its trigger so table mode cannot widen the toolbar.
    expect(wrapper.find('.columns-menu').exists()).toBe(false)
    await wrapper.find('.columns-trigger .view-toggle-btn').trigger('click')
    expect(wrapper.find('.columns-menu').exists()).toBe(true)

    const rarityButton = wrapper
      .findAll('.columns-menu .view-toggle-btn')
      .find((btn) => btn.text().includes('Rarity'))
    expect(rarityButton).toBeDefined()

    await rarityButton!.trigger('click')

    expect(store.tableColumns).toContain('rarity')
    expect(wrapper.find('.columns-menu').exists()).toBe(true)
  })

  it('applies a column preset', async () => {
    const wrapper = mount(DwellerDisplayControls, { props: { showView: true } })
    const store = useDwellerStore().filter

    store.setViewMode('table')
    await wrapper.vm.$nextTick()
    await wrapper.find('.columns-trigger .view-toggle-btn').trigger('click')

    const vitalsButton = wrapper
      .findAll('.columns-menu .view-toggle-btn')
      .find((btn) => btn.text().includes('Vitals'))
    expect(vitalsButton).toBeDefined()

    await vitalsButton!.trigger('click')

    expect(store.tableColumns).toContain('health')
    expect(store.tableColumns).not.toContain('room')
    expect(wrapper.find('.columns-menu').exists()).toBe(false)
  })

  it('styles its controls like the filter panel so the toolbar stays one control set', () => {
    expect(displayControlsSource).toMatch(
      /\.display-group :deep\(\.select-trigger\) \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
    )
    expect(displayControlsSource).toMatch(
      /\.sort-direction-button \{(?=[^}]*padding: 0\.5rem 0\.75rem;)[^}]*\}/
    )
    expect(displayControlsSource).toMatch(
      /\.view-toggle-btn \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
    )
    // The identity selects left behind in the panel must keep the same trigger metrics.
    expect(filterPanelSource).toMatch(
      /\.identity-controls :deep\(\.select-trigger\) \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
    )
    // The Display island reuses the panel's container treatment so the two pair up.
    expect(displayControlsSource).toMatch(
      /\.display-controls \{(?=[^}]*background: var\(--color-surface-sunken\);)(?=[^}]*border: 1px solid rgb\(from var\(--color-theme-primary\) r g b \/ 0\.2\);)[^}]*\}/
    )
    expect(filterPanelSource).toMatch(
      /\.filter-panel \{(?=[^}]*background: var\(--color-surface-sunken\);)(?=[^}]*border: 1px solid rgb\(from var\(--color-theme-primary\) r g b \/ 0\.2\);)[^}]*\}/
    )
  })

  it('selects with the same raised-surface treatment as the filter chips, never a fill', () => {
    expect(displayControlsSource).toMatch(
      /\.view-toggle-btn\.active \{[^}]*background: var\(--color-surface-hover\);/
    )
    expect(filterGroupSource).toMatch(
      /\.filter-chip\.active \{[^}]*background: var\(--color-surface-hover\);/
    )
    expect(filterGroupSource).not.toMatch(/background: var\(--color-theme-primary\);/)
  })
})
