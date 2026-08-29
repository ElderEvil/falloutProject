import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  goBack: vi.fn(),
  push: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/core/composables/useGoBack', () => ({
  useGoBack: () => ({ goBack: mocks.goBack }),
}))

import PageNavigation from '@/core/components/common/PageNavigation.vue'

describe('PageNavigation', () => {
  it('keeps the back button and breadcrumb trail together', () => {
    const wrapper = mount(PageNavigation, {
      props: {
        backLabel: 'Back to Dwellers',
        breadcrumbs: [
          { label: 'Vault', to: '/vault/vault-1' },
          { label: 'Dwellers', to: '/vault/vault-1/dwellers' },
          { label: 'Ada Lovelace' },
        ],
      },
    })

    expect(wrapper.get('button').attributes('aria-label')).toBe('Back to Dwellers')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('Breadcrumb')
    expect(wrapper.get('nav').text()).toContain('Vault')
    expect(wrapper.get('nav').text()).toContain('Dwellers')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Ada Lovelace')
  })

  it('uses the shared history-aware back behavior by default', async () => {
    const wrapper = mount(PageNavigation, { props: { breadcrumbs: [] } })

    await wrapper.get('button').trigger('click')

    expect(mocks.goBack).toHaveBeenCalledOnce()
  })
})
