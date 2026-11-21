import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, getActivePinia, setActivePinia } from 'pinia'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import QuestsView from '@/modules/progression/views/QuestsView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

// Regression for the vault-switch race: a load paused on the catalog fetch must not
// resume after a newer vault finished and overwrite its list. Kept separate from
// QuestsView.test.ts because that suite pins vue-router to a fixed vault id.

enableAutoUnmount(afterEach)
afterEach(() => {
  const pinia = getActivePinia()
  if (pinia) disposePinia(pinia)
})

const stubs = {
  SidePanel: true,
  PageContentRail: true,
  PageHeader: true,
  PageHeaderMetric: true,
  QuestCard: true,
  PartySelectionModal: true,
  QuestRewardsModal: true,
  Icon: true,
  Tabs: true,
  TabsList: true,
  TabsTrigger: true,
  Badge: true,
}

const questFixture = (id: string) => ({
  id,
  title: `Quest ${id}`,
  short_description: 'Fixture quest',
  long_description: 'Load-orchestration fixture',
  requirements: 'No prerequisites',
  rewards: '10 caps',
  quest_type: 'side',
  is_visible: true,
  is_completed: false,
})

describe('QuestsView vault-switch orchestration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not let a stale vault load overwrite the newer vault after the catalog fetch', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    const questStore = useQuestStore()
    const roomStore = useRoomStore()
    const { filter: dwellerStore } = useDwellerStore()

    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()

    // Vault A's catalog fetch is held back so vault B can finish loading first.
    let releaseACatalog!: () => void
    const catalogGate = new Promise<void>((resolve) => {
      releaseACatalog = resolve
    })
    let catalogCalls = 0
    const fetchAllQuests = vi.spyOn(questStore, 'fetchAllQuests').mockImplementation(async () => {
      catalogCalls += 1
      if (catalogCalls === 1) await catalogGate // Vault A waits; vault B does not.
    })
    const fetchVaultQuests = vi
      .spyOn(questStore, 'fetchVaultQuests')
      .mockImplementation(async (vaultId: string) => {
        if (vaultId !== 'vault-b') return
        questStore.vaultQuests = [questFixture('quest-b') as never]
      })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/vault/:id/quests', component: QuestsView },
      ],
    })
    await router.push('/vault/vault-a/quests')
    await router.isReady()
    mount(QuestsView, { global: { plugins: [router], stubs } })
    await flushPromises()
    expect(fetchVaultQuests).not.toHaveBeenCalled() // A is paused on the catalog fetch

    await router.push('/vault/vault-b/quests')
    await flushPromises()
    expect(questStore.vaultQuests.map((quest) => quest.id)).toEqual(['quest-b'])

    releaseACatalog()
    await flushPromises()

    // A resumed after the catalog fetch, hit the staleness recheck, and stopped
    // before publishing its own vault quests over B's.
    expect(questStore.vaultQuests.map((quest) => quest.id)).toEqual(['quest-b'])
    expect(fetchAllQuests).toHaveBeenCalledTimes(2)
    expect(fetchVaultQuests).toHaveBeenCalledTimes(1)
    expect(fetchVaultQuests).toHaveBeenCalledWith('vault-b')
  })
})
