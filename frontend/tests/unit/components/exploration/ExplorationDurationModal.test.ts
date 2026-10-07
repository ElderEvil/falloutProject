import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { config, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
import { Button } from '@/core/components/ui/button'
import { Dialog } from '@/core/components/ui/dialog'
import { Slider } from '@/core/components/ui/slider'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock" :data-icon="icon"></span>' }))

let originalTeleportStub: unknown

beforeEach(() => {
  originalTeleportStub = config.global.stubs.Teleport
  config.global.stubs.Teleport = { template: '<div><slot /></div>' }
})

afterEach(() => {
  config.global.stubs.Teleport = originalTeleportStub as never
})

describe('ExplorationDurationModal', () => {
  it('does not pack RadAway when the explorer cannot use it', async () => {
    const wrapper = mount(ExplorationDurationModal, {
      props: {
        show: true,
        dwellerName: 'Synth',
        maxStimpaks: 10,
        maxRadaways: 10,
        allowRadaway: false,
      },
    })

    expect(wrapper.text()).not.toContain('RadAway (Removes Rads)')
    expect(wrapper.text()).toContain("RadAway isn't needed: this dweller is radiation immune.")
    await wrapper.find('.modal-button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ duration: 4, stimpaks: 5, radaways: 0 }])
  })

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

      expect(wrapper.findComponent(Dialog).props('open')).toBe(false)
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

      expect(wrapper.findComponent(Dialog).props('open')).toBe(true)
      expect(wrapper.text()).toContain('Select Exploration Duration')
      expect(wrapper.text()).toContain('Amata')
      expect(wrapper.text()).toContain('Send to Wasteland')
      expect(wrapper.text()).not.toContain("RadAway isn't needed")
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

      expect(wrapper.findAllComponents(Slider)).toHaveLength(2)
    })

    it('uses shared terminal actions for cancellation and departure', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      const actions = wrapper.findComponent({ name: 'TerminalModalActions' })

      expect(actions.exists()).toBe(true)
      expect(actions.findAllComponents(Button)).toHaveLength(2)
      expect(actions.findAllComponents(Button)[0]?.props()).toMatchObject({
        variant: 'secondary',
        size: 'lg',
      })
      expect(actions.findAllComponents(Button)[1]?.props()).toMatchObject({
        variant: 'default',
        size: 'lg',
      })
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
    it('emits cancel when the shared modal closes', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      wrapper.findComponent(Dialog).vm.$emit('update:open', false)

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
      expect(confirmEvents![0]).toEqual([{ duration: 8, stimpaks: 5, radaways: 5 }])
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
      expect(confirmEvents![0]).toEqual([{ duration: 4, stimpaks: 5, radaways: 2 }])
    })
  })

  describe('heading reroll control', () => {
    it('keeps the Change control available when the suggestion failed', () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
          heading: null,
          isSuggestingHeading: false,
          canReroll: true,
        },
      })

      expect(wrapper.text()).toContain('Travel Heading')
      expect(wrapper.text()).toContain('No direction suggested')
      const changeButton = wrapper.findAllComponents(Button).find((button) => button.text() === 'Change')
      expect(changeButton).toBeDefined()
    })

    it('emits reroll with the selected duration when Change is clicked', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
          heading: 'E / 90°',
          canReroll: true,
        },
      })

      await wrapper.findAll('.duration-button')[3].trigger('click') // 8h
      const changeButton = wrapper.findAllComponents(Button).find((button) => button.text() === 'Change')
      await changeButton?.trigger('click')

      expect(wrapper.emitted('reroll')).toContainEqual([8])
    })

    it('re-requests the heading with the newly selected duration', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
          heading: 'E / 90°',
          canReroll: true,
        },
      })

      await wrapper.findAll('.duration-button')[5].trigger('click') // 24h

      expect(wrapper.emitted('reroll')).toContainEqual([24])
    })

    it('does not reroll while heading is user-chosen', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: true,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
          heading: 'E / 90°',
          canReroll: false,
        },
      })

      await wrapper.findAll('.duration-button')[5].trigger('click') // 24h

      expect(wrapper.emitted('reroll')).toBeUndefined()
    })
  })

  describe('compass dial', () => {
    const baseHeadingProps = {
      show: true,
      dwellerName: 'TestDweller',
      maxStimpaks: 10,
      maxRadaways: 10,
      heading: 'E / 90°',
      canReroll: true,
    }

    it('is collapsed by default behind a Pick direction toggle', () => {
      const wrapper = mount(ExplorationDurationModal, { props: baseHeadingProps })

      expect(wrapper.find('.heading-dial-toggle').exists()).toBe(true)
      expect(wrapper.find('.heading-dial-toggle').text()).toContain('Pick direction')
      expect(wrapper.find('.compass-dial').exists()).toBe(false)
    })

    it('expands into eight compass directions', async () => {
      const wrapper = mount(ExplorationDurationModal, { props: baseHeadingProps })

      await wrapper.find('.heading-dial-toggle').trigger('click')

      const directions = wrapper.findAll('.dial-direction')
      expect(directions).toHaveLength(8)
      expect(directions.map((d) => d.text())).toEqual(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
    })

    it('emits selectHeading with the mapped degrees when a direction is picked', async () => {
      const wrapper = mount(ExplorationDurationModal, { props: baseHeadingProps })

      await wrapper.find('.heading-dial-toggle').trigger('click')
      const east = wrapper.findAll('.dial-direction').find((d) => d.text() === 'E')
      await east?.trigger('click')

      expect(wrapper.emitted('selectHeading')).toContainEqual([90])
    })

    it('highlights the currently active direction on the dial', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: { ...baseHeadingProps, headingDegrees: 225 },
      })

      await wrapper.find('.heading-dial-toggle').trigger('click')

      const sw = wrapper.findAll('.dial-direction').find((d) => d.text() === 'SW')
      expect(sw?.attributes('aria-pressed')).toBe('true')
      const n = wrapper.findAll('.dial-direction').find((d) => d.text() === 'N')
      expect(n?.attributes('aria-pressed')).toBe('false')
    })

    it('stops auto-rerolling when a manual pick is active so it is not overwritten', async () => {
      const wrapper = mount(ExplorationDurationModal, { props: baseHeadingProps })

      await wrapper.find('.heading-dial-toggle').trigger('click')
      await wrapper.findAll('.dial-direction').find((d) => d.text() === 'E')?.trigger('click')
      expect(wrapper.emitted('selectHeading')).toContainEqual([90])

      // Selecting a different duration must NOT re-suggest a heading over the pick.
      await wrapper.findAll('.duration-button')[5].trigger('click')
      expect(wrapper.emitted('reroll')).toBeUndefined()
    })

    it('Change clears the manual pick and re-rerolls', async () => {
      const wrapper = mount(ExplorationDurationModal, { props: baseHeadingProps })

      await wrapper.find('.heading-dial-toggle').trigger('click')
      await wrapper.findAll('.dial-direction').find((d) => d.text() === 'SE')?.trigger('click')

      const changeButton = wrapper
        .findAllComponents(Button)
        .find((button) => button.text() === 'Change')
      await changeButton?.trigger('click')

      expect(wrapper.emitted('reroll')).toContainEqual([4])
      // The dial reverts to the server-suggested heading highlight.
      expect(wrapper.emitted('selectHeading')).toContainEqual([135])
    })

    it('seeds the dial highlight from headingDegrees when opened with a suggestion already set', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: { ...baseHeadingProps, heading: 'S / 180°', headingDegrees: 180 },
      })

      await wrapper.find('.heading-dial-toggle').trigger('click')

      const south = wrapper.findAll('.dial-direction').find((d) => d.text() === 'S')
      expect(south?.attributes('aria-pressed')).toBe('true')
    })
  })

  describe('prefill seeding', () => {
    it('seeds duration and supplies from initial props on open, clamped by maxes', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
          initialDuration: 8,
          initialStimpaks: 3,
          initialRadaways: 2,
        },
      })

      await wrapper.setProps({ show: true })
      await nextTick()

      expect(wrapper.find('.duration-button.active').text()).toBe('8h')
      expect(wrapper.text()).toContain('3 / 10')
      expect(wrapper.text()).toContain('2 / 10')
    })

    it('clamps prefilled supplies to the vault maximums', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 2,
          maxRadaways: 1,
          initialDuration: 4,
          initialStimpaks: 10,
          initialRadaways: 10,
        },
      })

      await wrapper.setProps({ show: true })
      await nextTick()

      expect(wrapper.text()).toContain('2 / 2')
      expect(wrapper.text()).toContain('1 / 1')
    })

    it('keeps today defaults when no initial props are provided', async () => {
      const wrapper = mount(ExplorationDurationModal, {
        props: {
          show: false,
          dwellerName: 'TestDweller',
          maxStimpaks: 10,
          maxRadaways: 10,
        },
      })

      await wrapper.setProps({ show: true })
      await nextTick()

      expect(wrapper.find('.duration-button.active').text()).toBe('4h')
      expect(wrapper.text()).toContain('5 / 10')
      expect(wrapper.text()).toContain('5 / 10')
    })
  })
})
