import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouterMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  goBack: vi.fn(),
  push: vi.fn(),
  back: vi.fn(),
}))

vi.mock('vue-router', () => createRouterMock({ push: mocks.push, back: mocks.back }))

vi.mock('@/core/composables/useGoBack', () => ({
  useGoBack: () => ({ goBack: mocks.goBack }),
}))

import PageNavigation from '@/core/components/common/PageNavigation.vue'

describe('PageNavigation', () => {
  beforeEach(() => {
    mocks.goBack.mockClear()
    mocks.push.mockClear()
    mocks.back.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

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

  it('prefers browser history when expanding a modal into a page', async () => {
    vi.spyOn(window.history, 'length', 'get').mockReturnValue(2)
    vi.spyOn(window.history, 'state', 'get').mockReturnValue({ back: '/vault/vault-1/map' })

    const wrapper = mount(PageNavigation, {
      props: {
        breadcrumbs: [],
        backTo: '/vault/vault-1/dwellers/dweller-1',
        historyFirst: true,
      },
    })

    await wrapper.get('button').trigger('click')

    expect(mocks.back).toHaveBeenCalledOnce()
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('keeps an explicit backTo when historyFirst is off', async () => {
    const wrapper = mount(PageNavigation, {
      props: { breadcrumbs: [], backTo: '/vault/vault-1/dwellers/dweller-1' },
    })

    await wrapper.get('button').trigger('click')

    expect(mocks.push).toHaveBeenCalledWith('/vault/vault-1/dwellers/dweller-1')
    expect(mocks.back).not.toHaveBeenCalled()
  })
})
