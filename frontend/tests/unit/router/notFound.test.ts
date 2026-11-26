import { beforeEach, describe, expect, it } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import router from '@/router'
import NotFoundView from '@/core/views/NotFoundView.vue'

beforeEach(async () => {
  setActivePinia(createPinia())
  localStorage.clear()
  await router.replace('/')
})

describe('unknown routes', () => {
  it('lands on the not-found route instead of silently ignoring the navigation', async () => {
    await router.push('/definitely-not-a-route')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('not-found')
    expect(router.currentRoute.value.path).toBe('/definitely-not-a-route')
  })

  it('renders a way back to the vault', () => {
    const wrapper = mount(NotFoundView, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Return to the vault')
  })
})
