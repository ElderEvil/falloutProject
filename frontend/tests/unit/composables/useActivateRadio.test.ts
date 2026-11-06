import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { ref } from 'vue'
import { useActivateRadio } from '@/modules/vault/composables/useActivateRadio'

const setRadioMode = vi.hoisted(() => vi.fn().mockResolvedValue({}))
const refreshVault = vi.hoisted(() => vi.fn().mockResolvedValue({}))
const authState = vi.hoisted(() => ({ token: 'token-1' as string | null }))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ error: vi.fn(), success: vi.fn() }),
}))

vi.mock('@/modules/radio/api/radio', () => ({ setRadioMode }))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => ({ refreshVault }) }))
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => authState }))

describe('useActivateRadio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.token = 'token-1'
  })

  it('switches the vault radio to happiness and refreshes it', async () => {
    const { handleActivateRadio, isActivatingRadio } = useActivateRadio(ref('vault-1'))

    await handleActivateRadio()

    expect(setRadioMode).toHaveBeenCalledWith('vault-1', 'happiness')
    expect(refreshVault).toHaveBeenCalledWith('vault-1', 'token-1')
    expect(isActivatingRadio.value).toBe(false)
  })

  it('does nothing when the user has no token', async () => {
    authState.token = null
    const { handleActivateRadio } = useActivateRadio(ref('vault-1'))

    await handleActivateRadio()

    expect(setRadioMode).not.toHaveBeenCalled()
    expect(refreshVault).not.toHaveBeenCalled()
  })
})
