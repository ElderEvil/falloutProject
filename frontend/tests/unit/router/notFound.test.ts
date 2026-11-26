import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import router from '@/router'
import NotFoundView from '@/core/views/NotFoundView.vue'

beforeEach(async () => {
  setActivePinia(createPinia())
  localStorage.clear()
  await router.replace('/')
})

describe('unknown routes', () => {
  it('lands on the not-found route instead of rendering nothing', async () => {
    await router.push('/definitely-not-a-route')

    expect(router.currentRoute.value.name).toBe('not-found')
    expect(router.currentRoute.value.path).toBe('/definitely-not-a-route')
  })

  it('names the page and offers a way back to the vault', async () => {
    const wrapper = mount(NotFoundView, { global: { plugins: [router] } })

    expect(wrapper.get('h1').text()).toContain('404')
    const push = vi.spyOn(router, 'push')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(push).toHaveBeenCalledWith('/')
  })
})
