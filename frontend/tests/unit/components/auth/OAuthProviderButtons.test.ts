import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { isTauri } from '@tauri-apps/api/core'
import { apiRequest } from '@/core/utils/api'
import OAuthProviderButtons from '@/modules/auth/components/OAuthProviderButtons.vue'

vi.mock('@tauri-apps/api/core', () => ({ isTauri: vi.fn() }))
vi.mock('@/core/utils/api', () => ({ apiRequest: vi.fn() }))

describe('OAuthProviderButtons', () => {
  beforeEach(() => {
    vi.mocked(isTauri).mockReturnValue(false)
    vi.mocked(apiRequest).mockReset()
    vi.mocked(apiRequest).mockResolvedValue({ data: { google: true, github: true } })
  })

  it('hides unsupported desktop authentication without discovering providers', async () => {
    vi.mocked(isTauri).mockReturnValue(true)
    const wrapper = mount(OAuthProviderButtons)
    await flushPromises()

    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(apiRequest).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps enabled authentication providers visible in the browser', async () => {
    const wrapper = mount(OAuthProviderButtons)
    await flushPromises()

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual([
      'CONTINUE WITH GOOGLE',
      'CONTINUE WITH GITHUB',
    ])
    wrapper.unmount()
  })

  it('hides disabled providers in the browser', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: { google: false, github: false } })
    const wrapper = mount(OAuthProviderButtons)
    await flushPromises()

    expect(wrapper.findAll('button')).toHaveLength(0)
    wrapper.unmount()
  })
})
