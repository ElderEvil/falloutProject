import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
import { UButton, USlider } from '@/core/components/ui'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

describe('ExplorationDurationModal', () => {
  describe('rendering', () => {
    it('renders nothing when show is false', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      expect(wrapper.find('.modal-overlay').exists()).toBe(false)
      expect(wrapper.text()).toBe('')
    })

    it('renders the modal when show is true', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'Amata',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      expect(wrapper.find('.modal-overlay').exists()).toBe(true)
      expect(wrapper.text()).toContain('Select Exploration Duration')
      expect(wrapper.text()).toContain('Amata')
      expect(wrapper.text()).toContain('Send to Wasteland')
    })

    it('renders all six duration options', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      const buttons = wrapper.findAll('.duration-button')
      expect(buttons).toHaveLength(6)
      expect(buttons[0].text()).toBe('1h')
      expect(buttons[5].text()).toBe('24h')
    })

    it('uses theme-primary accents for both medical supply sliders', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      expect(wrapper.findAllComponents(USlider)).toHaveLength(2)
      expect(wrapper.findAllComponents(USlider).every((slider) => slider.props('accent') === 'primary')).toBe(true)
      expect(wrapper.html()).not.toMatch(/bg-black|rgba\(|text-orange/)
    })

    it('uses matched terminal actions for cancellation and departure', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      const actions = wrapper.findAllComponents(UButton)

      expect(actions).toHaveLength(2)
      expect(actions[0].props()).toMatchObject({ variant: 'secondary', size: 'lg' })
      expect(actions[1].props()).toMatchObject({ variant: 'primary', size: 'lg' })
    })
  })

  describe('default state', () => {
    it('resets to default duration (4h) when opened', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      // Open the modal
      await wrapper.setProps({ show: true })
      await nextTick()

      // Default should be 4h
      const activeButton = wrapper.find('.duration-button.active')
      expect(activeButton.exists()).toBe(true)
      expect(activeButton.text()).toBe('4h')
    })

    it('resets to default stimpaks (clamped by max) when opened', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 3,
          maxRadaways: 10,
        },
      })

      await wrapper.setProps({ show: true })
      await nextTick()

      // maxStimpaks=3, DEFAULT=5 -> clamp to 3
      const supplyDisplay = wrapper.text()
      expect(supplyDisplay).toContain('3 / 3')
    })

    it('defaults stimpaks to min(5, maxStimpaks, 15)', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 20,
          maxRadaways: 20,
        },
      })

      await wrapper.setProps({ show: true })
      await nextTick()

      // maxStimpaks=20, DEFAULT=5 -> clamp to 5
      expect(wrapper.text()).toContain('5 / 20')
    })

    it('resets state every time the modal is reopened', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      // Open, change duration
      await wrapper.setProps({ show: true })
      await nextTick()
      await wrapper.findAll('.duration-button')[2].trigger('click') // 4h -> already default
      await wrapper.findAll('.duration-button')[5].trigger('click') // 24h

      // Close
      await wrapper.setProps({ show: false })
      await nextTick()

      // Reopen - should reset to 4h
      await wrapper.setProps({ show: true })
      await nextTick()

      const activeButton = wrapper.find('.duration-button.active')
      expect(activeButton.text()).toBe('4h')
    })
  })

  describe('emits', () => {
    it('emits cancel on overlay click', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      await wrapper.find('.modal-overlay').trigger('click')

      expect(wrapper.emitted('cancel')).toHaveLength(1)
    })

    it('emits cancel on Cancel button click', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      await wrapper.find('.modal-button.cancel').trigger('click')

      expect(wrapper.emitted('cancel')).toHaveLength(1)
    })

    it('emits confirm with correct payload', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 5,
        },
      })

      // Select 8h duration (index 3)
      await wrapper.findAll('.duration-button')[3].trigger('click')

      await wrapper.find('.modal-button.confirm').trigger('click')

      const confirmEvents = wrapper.emitted('confirm')
      expect(confirmEvents).toHaveLength(1)
      expect(confirmEvents![0]).toEqual([
        { duration: 8, stimpaks: 5, radaways: 5 },
      ])
    })

    it('confirm respects default stimpak clamp with low maxRadaways', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 2,
        },
      })

      await wrapper.find('.modal-button.confirm').trigger('click')

      const confirmEvents = wrapper.emitted('confirm')
      // radaways clamped to min(5, 2, 15) = 2
      expect(confirmEvents![0]).toEqual([
        { duration: 4, stimpaks: 5, radaways: 2 },
      ])
    })
  })

  describe('content click does not close', () => {
    it('does not emit cancel when clicking modal content', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      await wrapper.find('.modal-content').trigger('click')

      expect(wrapper.emitted('cancel')).toBeUndefined()
    })
  })
})
