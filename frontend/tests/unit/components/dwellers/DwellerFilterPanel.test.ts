import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerFilterPanel from '@/modules/dwellers/components/DwellerFilterPanel.vue'
import { useDwellerStore } from '@/stores/dweller'

describe('DwellerFilterPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('Status Filters', () => {
    it('should render all status filter options', () => {
      const wrapper = mount(DwellerFilterPanel)

      // Check for all status options
      expect(wrapper.text()).toContain('All')
      expect(wrapper.text()).toContain('Idle')
      expect(wrapper.text()).toContain('Working')
      expect(wrapper.text()).toContain('Training')
      expect(wrapper.text()).toContain('Exploring')
      expect(wrapper.text()).toContain('Questing')
      expect(wrapper.text()).toContain('Dead')
    })

    it('should update store when status filter is clicked', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore()

      // Find and click the "Working" filter button
      const buttons = wrapper.findAll('.filter-button')
      const workingButton = buttons.find(btn => btn.text().includes('Working'))

      expect(workingButton).toBeDefined()
      await workingButton!.trigger('click')

      expect(store.filterStatus).toBe('working')
    })

    it('should highlight active filter with active class', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore()

      store.setFilterStatus('working')
      await wrapper.vm.$nextTick()

      // Check that the working filter has active class
      const buttons = wrapper.findAll('.filter-button')
      const workingButton = buttons.find(btn => btn.text().includes('Working'))

      expect(workingButton!.classes()).toContain('active')
    })
  })

  describe('Sort Options', () => {
    it('should render sort by section', () => {
      const wrapper = mount(DwellerFilterPanel)

      expect(wrapper.text()).toContain('Sort By')
    })

    it('should update store when sort option is changed', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore()

      const sortSelect = wrapper.find('.sort-select')
      await sortSelect.setValue('level')

      expect(store.sortBy).toBe('level')
    })

    it('should have sort direction toggle button', () => {
      const wrapper = mount(DwellerFilterPanel)

      const sortDirectionBtn = wrapper.find('.sort-direction-button')
      expect(sortDirectionBtn.exists()).toBe(true)
    })
  })

  describe('Component Structure', () => {
    it('should render filter panel container', () => {
      const wrapper = mount(DwellerFilterPanel)

      const filterPanel = wrapper.find('.filter-panel')
      expect(filterPanel.exists()).toBe(true)
    })

    it('should have button group for status filters', () => {
      const wrapper = mount(DwellerFilterPanel)

      const buttonGroup = wrapper.find('.button-group')
      expect(buttonGroup.exists()).toBe(true)
    })
  })
})
