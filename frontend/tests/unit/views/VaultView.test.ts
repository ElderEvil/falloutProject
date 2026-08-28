import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import VaultView from '@/modules/vault/views/VaultView.vue'

describe('VaultView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses the terminal surface for the vault loading error', async () => {
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
    const errorCard = wrapper.find('h2').element.parentElement

    expect(wrapper.text()).toContain('Error Loading Vault')
    expect(errorCard?.classList).toContain('bg-surface-raised')
    expect(errorCard?.classList).not.toContain('bg-gray-900')
  })
})
