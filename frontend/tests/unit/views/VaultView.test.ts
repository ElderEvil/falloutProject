import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import VaultView from '@/modules/vault/views/VaultView.vue'

describe('VaultView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the vault loading error state with a way back', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/vault/:id?', component: VaultView },
      ],
    })
    await router.push('/vault/test-vault')
    await router.isReady()

    const wrapper = mount(VaultView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('h2').text()).toContain('Error Loading Vault')
    expect(wrapper.text()).toContain('Go to Vault List')
  })
})
