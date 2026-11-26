import { afterEach, beforeEach, describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { config, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
import { Button } from '@/core/components/ui/button'
import { Dialog } from '@/core/components/ui/dialog'
import { Slider } from '@/core/components/ui/slider'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

let originalTeleportStub: unknown

beforeEach(() => {
  originalTeleportStub = config.global.stubs.Teleport
  config.global.stubs.Teleport = { template: '<div><slot /></div>' }
})

afterEach(() => {
  config.global.stubs.Teleport = originalTeleportStub as never
})

const DEFAULT_PROPS = { show: true, dwellerName: 'TestDweller', maxStimpaks: 10, maxRadaways: 10 }
const DURATIONS = [1, 2, 4, 8, 12, 24]
const HEADING_PROPS = { heading: 'E / 90°', canReroll: true }

const mountModal = (props: Record<string, unknown> = {}) =>
  mount(ExplorationDurationModal, { props: { ...DEFAULT_PROPS, ...props } })

/** Mount closed, then open it: the reset-on-open behaviour needs both transitions. */
const openModal = async (props: Record<string, unknown> = {}) => {
  const wrapper = mountModal({ ...props, show: false })
  await wrapper.setProps({ show: true })
  await nextTick()
  return wrapper
}

const pickDuration = (wrapper: VueWrapper, hours: number) =>
  wrapper.findAll('.duration-button')[DURATIONS.indexOf(hours)]!.trigger('click')

const changeButton = (wrapper: VueWrapper) =>
  wrapper.findAllComponents(Button).find((button) => button.text() === 'Change')

const dialDirections = async (wrapper: VueWrapper) => {
  await wrapper.find('.heading-dial-toggle').trigger('click')
  return wrapper.findAll('.dial-direction')
}

const pickDirection = async (wrapper: VueWrapper, label: string) => {
  const directions = await dialDirections(wrapper)
  await directions.find((direction) => direction.text() === label)!.trigger('click')
}

describe('ExplorationDurationModal', () => {
  it('does not pack RadAway when the explorer cannot use it', async () => {
    const wrapper = mountModal({ dwellerName: 'Synth', allowRadaway: false })

    expect(wrapper.text()).not.toContain('RadAway (Removes Rads)')
    expect(wrapper.text()).toContain("RadAway isn't needed: this dweller is radiation immune.")
    await wrapper.find('.modal-button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ duration: 4, stimpaks: 5, radaways: 0 }])
  })

  describe('rendering', () => {
    it('renders nothing when show is false', () => {
      const wrapper = mountModal({ show: false })

      expect(wrapper.findComponent(Dialog).props('open')).toBe(false)
      expect(wrapper.text()).toBe('')
    })

    it('renders the modal and its six duration options when show is true', () => {
      const wrapper = mountModal({ dwellerName: 'Amata' })

      expect(wrapper.findComponent(Dialog).props('open')).toBe(true)
      expect(wrapper.text()).toContain('Select Exploration Duration')
      expect(wrapper.text()).toContain('Amata')
      expect(wrapper.text()).toContain('Send to Wasteland')
      expect(wrapper.text()).not.toContain("RadAway isn't needed")
      const buttons = wrapper.findAll('.duration-button')
      expect(buttons).toHaveLength(6)
      expect(buttons[0].text()).toBe('1h')
      expect(buttons[5].text()).toBe('24h')
    })

    it('uses theme-primary accents for both medical supply sliders', () => {
      expect(mountModal().findAllComponents(Slider)).toHaveLength(2)
    })

    it('uses shared terminal actions for cancellation and departure', () => {
      const actions = mountModal().findComponent({ name: 'TerminalModalActions' })
      const buttons = actions.findAllComponents(Button)

      expect(actions.exists()).toBe(true)
      expect(buttons).toHaveLength(2)
      expect(buttons[0]?.props()).toMatchObject({ variant: 'secondary', size: 'lg' })
      expect(buttons[1]?.props()).toMatchObject({ variant: 'default', size: 'lg' })
    })
  })

  describe('default state', () => {
    it.each([
      [3, '3 / 3'], // DEFAULT=5 clamps down to the vault stock.
      [20, '5 / 20'], // DEFAULT=5 stays put under a generous stock.
    ])('defaults stimpaks to min(5, maxStimpaks, 15) (max %i)', async (maxStimpaks, expected) => {
      const wrapper = await openModal({ maxStimpaks })

      expect(wrapper.text()).toContain(expected)
    })

    it('resets state every time the modal is reopened', async () => {
      const wrapper = await openModal()

      await pickDuration(wrapper, 24)
      await wrapper.setProps({ show: false })
      await nextTick()
      await wrapper.setProps({ show: true })
      await nextTick()

      expect(wrapper.find('.duration-button.active').text()).toBe('4h')
    })
  })

  describe('emits', () => {
    it('emits cancel when the shared modal closes', () => {
      const wrapper = mountModal()

      wrapper.findComponent(Dialog).vm.$emit('update:open', false)

      expect(wrapper.emitted('cancel')).toHaveLength(1)
    })

    it('emits cancel on Cancel button click', async () => {
      const wrapper = mountModal()

      await wrapper.find('.modal-button.cancel').trigger('click')

      expect(wrapper.emitted('cancel')).toHaveLength(1)
    })

    it('emits confirm with correct payload', async () => {
      const wrapper = mountModal({ maxRadaways: 5 })

      await pickDuration(wrapper, 8)
      await wrapper.find('.modal-button.confirm').trigger('click')

      expect(wrapper.emitted('confirm')).toHaveLength(1)
      expect(wrapper.emitted('confirm')![0]).toEqual([{ duration: 8, stimpaks: 5, radaways: 5 }])
    })

    it('confirm respects default stimpak clamp with low maxRadaways', async () => {
      const wrapper = mountModal({ maxRadaways: 2 })

      await wrapper.find('.modal-button.confirm').trigger('click')

      // radaways clamped to min(5, 2, 15) = 2
      expect(wrapper.emitted('confirm')![0]).toEqual([{ duration: 4, stimpaks: 5, radaways: 2 }])
    })
  })

  describe('heading reroll control', () => {
    it('keeps the Change control available when the suggestion failed', () => {
      const wrapper = mountModal({ heading: null, isSuggestingHeading: false, canReroll: true })

      expect(wrapper.text()).toContain('Travel Heading')
      expect(wrapper.text()).toContain('No direction suggested')
      expect(changeButton(wrapper)).toBeDefined()
    })

    it('emits reroll with the selected duration when Change is clicked', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      await pickDuration(wrapper, 8)
      await changeButton(wrapper)?.trigger('click')

      expect(wrapper.emitted('reroll')).toContainEqual([8])
    })

    it('re-requests the heading with the newly selected duration', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      await pickDuration(wrapper, 24)

      expect(wrapper.emitted('reroll')).toContainEqual([24])
    })

    it('does not reroll while heading is user-chosen', async () => {
      const wrapper = mountModal({ ...HEADING_PROPS, canReroll: false })

      await pickDuration(wrapper, 24)

      expect(wrapper.emitted('reroll')).toBeUndefined()
    })
  })

  describe('compass dial', () => {
    it('is collapsed by default behind a Pick direction toggle', () => {
      const wrapper = mountModal(HEADING_PROPS)

      expect(wrapper.find('.heading-dial-toggle').exists()).toBe(true)
      expect(wrapper.find('.heading-dial-toggle').text()).toContain('Pick direction')
      expect(wrapper.find('.compass-dial').exists()).toBe(false)
    })

    it('expands into eight compass directions', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      const directions = await dialDirections(wrapper)

      expect(directions).toHaveLength(8)
      expect(directions.map((direction) => direction.text())).toEqual([
        'N',
        'NE',
        'E',
        'SE',
        'S',
        'SW',
        'W',
        'NW',
      ])
    })

    it('emits selectHeading with the mapped degrees when a direction is picked', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      await pickDirection(wrapper, 'E')

      expect(wrapper.emitted('selectHeading')).toContainEqual([90])
    })

    it('highlights the currently active direction on the dial', async () => {
      const wrapper = mountModal({ ...HEADING_PROPS, headingDegrees: 225 })

      const directions = await dialDirections(wrapper)

      expect(
        directions.find((direction) => direction.text() === 'SW')?.attributes('aria-pressed')
      ).toBe('true')
      expect(
        directions.find((direction) => direction.text() === 'N')?.attributes('aria-pressed')
      ).toBe('false')
    })

    it('stops auto-rerolling when a manual pick is active so it is not overwritten', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      await pickDirection(wrapper, 'E')
      expect(wrapper.emitted('selectHeading')).toContainEqual([90])

      // Selecting a different duration must NOT re-suggest a heading over the pick.
      await pickDuration(wrapper, 24)
      expect(wrapper.emitted('reroll')).toBeUndefined()
    })

    it('Change clears the manual pick and re-rerolls', async () => {
      const wrapper = mountModal(HEADING_PROPS)

      await pickDirection(wrapper, 'SE')
      await changeButton(wrapper)?.trigger('click')

      expect(wrapper.emitted('reroll')).toContainEqual([4])
      // The dial reverts to the server-suggested heading highlight.
      expect(wrapper.emitted('selectHeading')).toContainEqual([135])
    })

    it('seeds the dial highlight from headingDegrees when opened with a suggestion already set', async () => {
      const wrapper = mountModal({ ...HEADING_PROPS, heading: 'S / 180°', headingDegrees: 180 })

      const directions = await dialDirections(wrapper)

      expect(
        directions.find((direction) => direction.text() === 'S')?.attributes('aria-pressed')
      ).toBe('true')
    })
  })

  describe('prefill seeding', () => {
    it.each([
      [{ initialDuration: 8, initialStimpaks: 3, initialRadaways: 2 }, '8h', ['3 / 10', '2 / 10']],
      [
        {
          maxStimpaks: 2,
          maxRadaways: 1,
          initialDuration: 4,
          initialStimpaks: 10,
          initialRadaways: 10,
        },
        '4h',
        ['2 / 2', '1 / 1'],
      ],
      [{}, '4h', ['5 / 10']],
    ])(
      'seeds duration and supplies on open, clamped by maxes (%#)',
      async (props, duration, supplies) => {
        const wrapper = await openModal(props)

        const active = wrapper.find('.duration-button.active')
        expect(active.exists()).toBe(true)
        expect(active.text()).toBe(duration)
        for (const supply of supplies) expect(wrapper.text()).toContain(supply)
      }
    )
  })
})
