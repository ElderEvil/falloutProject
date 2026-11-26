import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerDisplayControls from '@/modules/dwellers/components/DwellerDisplayControls.vue'
import { audioManager } from '@/core/audio/audioManager'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { DEFAULT_TABLE_COLUMNS } from '@/modules/dwellers/models/dwellerTable'

vi.mock('@/core/audio/audioManager', () => ({
  audioManager: { play: vi.fn() },
}))

describe('DwellerDisplayControls', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  const mountControls = (props: { showView?: boolean } = {}) =>
    mount(DwellerDisplayControls, { props })
  const store = () => useDwellerStore().filter
  const toggleButton = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.view-toggle-btn').find((btn) => btn.text().includes(label))!

  const openColumnMenu = async (wrapper: ReturnType<typeof mount>) => {
    store().setViewMode('table')
    await wrapper.vm.$nextTick()
    await wrapper.find('.columns-trigger .view-toggle-btn').trigger('click')
  }

  it('renders the sort control and no view toggle by default', () => {
    const wrapper = mountControls()

    expect(wrapper.find('.display-group [role="combobox"]').attributes('aria-label')).toBe(
      'Sort dwellers'
    )
    expect(wrapper.find('.sort-direction-button').exists()).toBe(true)
    expect(wrapper.find('.view-toggle-btn').exists()).toBe(false)
  })

  it('updates the store when the sort option changes', async () => {
    const wrapper = mountControls()

    // reka-ui opens the listbox on pointerdown and selects on pointerup (not click).
    wrapper
      .find('.display-group [role="combobox"]')
      .element.dispatchEvent(new MouseEvent('pointerdown', { button: 0, bubbles: true }))
    await flushPromises()

    const levelOption = Array.from(document.body.querySelectorAll('[role="option"]')).find(
      (option) => option.textContent?.includes('Level')
    ) as HTMLElement
    expect(levelOption).toBeDefined()
    levelOption.dispatchEvent(new MouseEvent('pointerup', { button: 0, bubbles: true }))
    await flushPromises()

    expect(store().sortBy).toBe('level')
  })

  it('toggles the sort direction', async () => {
    const wrapper = mountControls()
    expect(store().sortDirection).toBe('asc')

    await wrapper.find('.sort-direction-button').trigger('click')

    expect(store().sortDirection).toBe('desc')
  })

  it.each([
    ['Table', 'table', true],
    ['Grid', 'grid', true],
    ['List', 'list', false],
  ] as const)(
    'switches to the %s view and plays the tab sound only on a change (%s)',
    async (label, viewMode, sounds) => {
      const wrapper = mountControls({ showView: true })

      await toggleButton(wrapper, label).trigger('click')

      expect(store().viewMode).toBe(viewMode)
      if (sounds) expect(audioManager.play).toHaveBeenCalledWith('tabSwitch', 'ui')
      else expect(audioManager.play).not.toHaveBeenCalled()
    }
  )

  it('shows the column picker only in table mode and toggles a column', async () => {
    const wrapper = mountControls({ showView: true })
    expect(wrapper.find('.columns-trigger').exists()).toBe(false)

    await openColumnMenu(wrapper)

    // The picker is collapsed behind its trigger so table mode cannot widen the toolbar.
    expect(wrapper.find('.columns-menu').exists()).toBe(true)
    const rarity = wrapper
      .findAll('.columns-menu .view-toggle-btn')
      .find((btn) => btn.text().includes('Rarity'))!
    await rarity.trigger('click')

    expect(store().tableColumns).toContain('rarity')
    expect(wrapper.find('.columns-menu').exists()).toBe(true)
  })

  it('applies a preset and resets the columns back to the defaults', async () => {
    const wrapper = mountControls({ showView: true })
    await openColumnMenu(wrapper)

    const vitals = wrapper
      .findAll('.columns-menu .view-toggle-btn')
      .find((btn) => btn.text().includes('Vitals'))!
    await vitals.trigger('click')

    expect(store().tableColumns).toContain('health')
    expect(store().tableColumns).not.toContain('room')
    expect(wrapper.find('.columns-menu').exists()).toBe(false)

    store().setViewMode('table')
    await wrapper.vm.$nextTick()
    await wrapper.find('.columns-trigger .view-toggle-btn').trigger('click')
    await wrapper.find('.preset-reset').trigger('click')

    expect(store().tableColumns).toEqual(DEFAULT_TABLE_COLUMNS)
  })
})
