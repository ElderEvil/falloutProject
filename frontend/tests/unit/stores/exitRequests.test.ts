import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import axios from '@/core/plugins/axios'
import { useExitRequestStore } from '@/modules/dwellers/stores/exitRequests'
import ExitRequestModal from '@/modules/dwellers/components/modals/ExitRequestModal.vue'

const toastMock = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMock,
}))

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>',
  },
}))

vi.mock('@/core/components/ui/UModal.vue', () => ({
  default: {
    name: 'UModal',
    props: ['modelValue', 'title', 'size'],
    emits: ['update:modelValue', 'close'],
    template: '<div v-if="modelValue" class="mock-modal"><slot /></div>',
  },
}))

vi.mock('@/core/components/ui/UButton.vue', () => ({
  default: {
    name: 'UButton',
    props: ['disabled', 'variant'],
    template: '<button class="mock-button" :disabled="disabled"><slot /></button>',
  },
}))

vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({ activeVaultId: 'vault-1' }),
}))

const pendingRequest = {
  dweller_id: 'dweller-1',
  dweller_name: 'Alice Smith',
  level: 5,
  happiness: 30,
}

describe('useExitRequestStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads the pending exit requests for the vault', async () => {
    const store = useExitRequestStore()
    vi.mocked(axios.get).mockResolvedValue({
      data: [pendingRequest],
    })

    await store.load('vault-1')

    expect(axios.get).toHaveBeenCalledWith('/api/v1/dwellers/vault/vault-1/exit-requests')
    expect(store.requests).toEqual([pendingRequest])
    expect(store.isLoading).toBe(false)
  })

  it('shows an error toast when loading fails', async () => {
    const store = useExitRequestStore()
    vi.mocked(axios.get).mockRejectedValue(new Error('boom'))

    await store.load('vault-1')

    expect(store.requests).toEqual([])
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining('Failed to load exit requests'))
  })

  it('grants an exit request and removes the dweller from the pending list', async () => {
    const store = useExitRequestStore()
    store.requests = [pendingRequest]
    vi.mocked(axios.post).mockResolvedValue({
      data: { dweller_id: 'dweller-1', dweller_name: 'Alice Smith', granted: true, happiness: 30 },
    })

    const result = await store.grant('vault-1', 'dweller-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/dwellers/dweller-1/grant-exit')
    expect(result).toBe(true)
    expect(store.requests).toEqual([])
    expect(toastMock.warning).toHaveBeenCalledWith(expect.stringContaining('walked out'))
  })

  it('refuses an exit request and updates the dweller happiness', async () => {
    const store = useExitRequestStore()
    store.requests = [pendingRequest]
    vi.mocked(axios.post).mockResolvedValue({
      data: { dweller_id: 'dweller-1', dweller_name: 'Alice Smith', granted: false, happiness: 20 },
    })

    const result = await store.refuse('vault-1', 'dweller-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/dwellers/dweller-1/refuse-exit')
    expect(result).toBe(true)
    expect(store.requests[0].happiness).toBe(20)
    expect(toastMock.info).toHaveBeenCalledWith(expect.stringContaining('was refused'))
  })

  it('keeps the request standing when refusing fails', async () => {
    const store = useExitRequestStore()
    store.requests = [pendingRequest]
    vi.mocked(axios.post).mockRejectedValue(new Error('boom'))

    const result = await store.refuse('vault-1', 'dweller-1')

    expect(result).toBe(false)
    expect(store.requests).toEqual([pendingRequest])
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining('Failed to refuse'))
  })
})

describe('ExitRequestModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens for a pending request and closes without deciding when dismissed', async () => {
    vi.mocked(axios.get).mockResolvedValue({
      data: [pendingRequest],
    })

    const wrapper = mount(ExitRequestModal, {
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.find('.mock-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('Alice Smith')

    const decideLater = wrapper.findAll('button').find((button) => button.text().includes('Decide Later'))
    await decideLater!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.mock-modal').exists()).toBe(false)
    expect(useExitRequestStore().requests).toEqual([pendingRequest])
  })
})
