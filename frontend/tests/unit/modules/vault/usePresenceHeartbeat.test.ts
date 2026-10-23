import { describe, expect, it, vi, beforeEach, afterEach } from 'vite-plus/test'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { usePresenceHeartbeat } from '@/modules/vault/composables/usePresenceHeartbeat'

const setVisibility = (state: 'visible' | 'hidden'): void => {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true })
}

const mountHeartbeat = (vaultId: string | null = 'vault-1', token: string | null = 'token') => {
  const Host = defineComponent({
    setup() {
      usePresenceHeartbeat(
        () => vaultId,
        () => token
      )
      return () => h('div')
    },
  })
  return mount(Host)
}

describe('usePresenceHeartbeat', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setVisibility('visible')
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('pings on mount and every interval while the overview is visible', async () => {
    const ping = vi.spyOn(useVaultStore(), 'pingPresence').mockResolvedValue(undefined)
    mountHeartbeat()
    await flushPromises()

    expect(ping).toHaveBeenCalledTimes(1)
    expect(ping).toHaveBeenCalledWith('vault-1', 'token')

    await vi.advanceTimersByTimeAsync(30_000)
    expect(ping).toHaveBeenCalledTimes(2)
  })

  it('stays silent while the tab is hidden and resumes when visible', async () => {
    const ping = vi.spyOn(useVaultStore(), 'pingPresence').mockResolvedValue(undefined)
    mountHeartbeat()
    await flushPromises()
    expect(ping).toHaveBeenCalledTimes(1)

    setVisibility('hidden')
    await vi.advanceTimersByTimeAsync(120_000)
    expect(ping).toHaveBeenCalledTimes(1)

    setVisibility('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(ping).toHaveBeenCalledTimes(2)
  })

  it('never pings without a vault or a token', async () => {
    const ping = vi.spyOn(useVaultStore(), 'pingPresence').mockResolvedValue(undefined)
    mountHeartbeat(null, null)
    await flushPromises()

    await vi.advanceTimersByTimeAsync(60_000)
    expect(ping).not.toHaveBeenCalled()
  })
})
