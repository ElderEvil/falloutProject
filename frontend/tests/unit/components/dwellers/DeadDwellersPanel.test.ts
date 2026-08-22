import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import DeadDwellersPanel from '@/modules/dwellers/components/DeadDwellersPanel.vue'

describe('DeadDwellersPanel', () => {
  it('renders the empty deceased-dwellers state', () => {
    const wrapper = shallowMount(DeadDwellersPanel, {
      props: {
        dwellers: [],
        isLoading: false,
        revivingDwellers: {},
      },
      global: {
        stubs: {
          UButton: { template: '<button><slot /></button>' },
          TerminalEmptyState: {
            props: ['title', 'description'],
            template: '<section><h3>{{ title }}</h3><p>{{ description }}</p><slot name="actions" /></section>',
          },
        },
      },
    })

    expect(wrapper.text()).toContain('No Dead Dwellers')
    expect(wrapper.text()).toContain('View Graveyard')
  })
})
