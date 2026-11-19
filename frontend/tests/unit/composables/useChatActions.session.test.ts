import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { ref } from 'vue'
import { useChatActions } from '@/modules/chat/composables/useChatActions'
import { appendBioAddendum } from '@/modules/dwellers/services/dwellerService'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import type { ActionSuggestion, ChatMessageDisplay } from '@/modules/chat/models/chat'

const state = vi.hoisted(() => ({
  auth: { token: 'token', sessionGeneration: 0 },
  filter: { detailedDwellers: {} as Record<string, unknown> },
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => state.auth }))
vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({ filter: state.filter, management: {} }),
}))
vi.mock('@/modules/dwellers/services/dwellerService', () => ({ appendBioAddendum: vi.fn() }))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => ({}) }))
vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: () => ({}) }))
vi.mock('@/modules/exploration/stores/exploration', () => ({ useExplorationStore: () => ({}) }))
vi.mock('@/modules/dwellers/stores/dwellerMedical', () => ({ useDwellerMedicalStore: () => ({}) }))
vi.mock('@/modules/map/stores/map', () => ({ useMapStore: () => ({}) }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => ({ success: state.success }) }))
vi.mock('@/core/utils/errorHandler', () => ({ notifyErrorOnce: state.error }))

describe('biography action session ownership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.auth.sessionGeneration = 0
    state.filter.detailedDwellers = {}
  })

  it.each(['current', 'obsolete', 'failed'] as const)(
    'handles a %s biography completion',
    async (outcome) => {
      const { promise, resolve, reject } = Promise.withResolvers<Dweller>()
      vi.mocked(appendBioAddendum).mockReturnValueOnce(promise)
      const action = {
        action_type: 'bio_addendum',
        bio_text: 'A new memory',
        reason: 'Remember',
      } as ActionSuggestion
      const messages = ref([{ actionSuggestion: action }] as ChatMessageDisplay[])
      const actions = useChatActions({ dwellerId: 'd1', dwellerName: 'Ash', messages })
      const pending = actions.handleActionConfirm(action, 0)
      if (outcome !== 'current') state.auth.sessionGeneration++
      const updated = { id: 'd1' } as Dweller
      if (outcome === 'failed') reject(new Error('Old failure'))
      else resolve(updated)
      await pending
      if (outcome === 'current') {
        expect(state.filter.detailedDwellers.d1).toEqual(updated)
        expect(state.success).toHaveBeenCalledOnce()
        expect(messages.value[0].actionSuggestion).toBeNull()
      } else {
        expect(state.filter.detailedDwellers).toEqual({})
        expect(state.success).not.toHaveBeenCalled()
        expect(state.error).not.toHaveBeenCalled()
        expect(messages.value[0].actionSuggestion).toEqual(action)
      }
      expect(actions.isPerformingAction.value).toBe(false)
    }
  )
})
