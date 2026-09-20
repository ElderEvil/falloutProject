import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PregnancyCard from '@/modules/social/components/pregnancy/PregnancyCard.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

vi.mock('@/modules/social/stores/pregnancy', () => ({
  usePregnancyStore: () => ({
    formatTimeRemaining: (seconds: number) => `${seconds}s`,
  }),
}))

const mother = {
  id: 'm1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 5,
  thumbnail_url: null,
  gender: 'female',
}

const father = {
  id: 'f1',
  first_name: 'Bob',
  last_name: 'Jones',
  level: 7,
  thumbnail_url: null,
  gender: 'male',
}

const pregnancy = {
  id: 'p1',
  mother_id: 'm1',
  father_id: 'f1',
  conceived_at: '2026-01-01T00:00:00Z',
  due_at: '2026-01-01T03:00:00Z',
  status: 'pregnant',
  progress_percentage: 50,
  time_remaining_seconds: 5400,
  is_due: false,
}

function createWrapper(props: Record<string, unknown> = {}) {
  return mount(PregnancyCard, {
    props: {
      pregnancy,
      mother,
      father,
      ...props,
    },
    global: {
      stubs: {
        UCard: { template: '<div class="ucard-stub"><slot /></div>' },
        UBadge: { template: '<span class="ubadge-stub"><slot /></span>' },
        UButton: { template: '<button class="ubutton-stub"><slot /></button>' },
        DwellerPortrait: {
          template: '<span class="dweller-portrait-stub" :data-alt="alt" />',
          props: ['alt'],
        },
      },
    },
  })
}

describe('PregnancyCard', () => {
  it('renders parent names and portraits from dweller objects', () => {
    const wrapper = createWrapper()

    expect(wrapper.text()).toContain('Alice Smith')
    expect(wrapper.text()).toContain('Bob Jones')

    const portraits = wrapper.findAll('.dweller-portrait-stub')
    expect(portraits).toHaveLength(2)
    expect(portraits[0].attributes('data-alt')).toBe('Alice Smith')
    expect(portraits[1].attributes('data-alt')).toBe('Bob Jones')
  })

  it('renders the status badge and progress meter', () => {
    const wrapper = createWrapper()

    expect(wrapper.text()).toContain('pregnant')
    expect(wrapper.text()).toContain('Progress: 50%')
  })

  it('shows the deliver button when the pregnancy is due', () => {
    const wrapper = createWrapper({ pregnancy: { ...pregnancy, is_due: true } })

    expect(wrapper.text()).toContain('Deliver Baby')
  })

  it('hides the deliver button when not due', () => {
    const wrapper = createWrapper()

    expect(wrapper.text()).not.toContain('Deliver Baby')
  })

  it('emits deliver when the deliver button is clicked', async () => {
    const wrapper = createWrapper({ pregnancy: { ...pregnancy, is_due: true } })

    await wrapper.get('.ubutton-stub').trigger('click')

    expect(wrapper.emitted('deliver')).toBeTruthy()
  })

  it('handles a null last name', () => {
    const wrapper = createWrapper({ mother: { ...mother, last_name: null } })

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).not.toContain('Alice null')
  })
})
