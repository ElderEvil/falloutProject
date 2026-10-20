import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock, createIconifyMock, createToastMock } from '../helpers/mocks'
import { defineComponent, h, ref, type App } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { VueQueryPlugin } from '@tanstack/vue-query'
import axios from '@/core/plugins/axios'
import { queryClient as appQueryClient } from '@/core/query/queryClient'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { User } from '@/modules/auth/types/user'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'
import {
  useNukaColaCount,
  type NukaColaCountState,
} from '@/modules/vault/composables/useNukaColaCount'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { StorageItemsResponse } from '@/modules/storage/services/storageService'
import StorageView from '@/modules/storage/views/StorageView.vue'
import LunchboxOpenModal from '@/modules/storage/components/LunchboxOpenModal.vue'
import { mountWithSetup } from '../helpers/mountWithSetup'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

vi.mock('@iconify/vue', () => createIconifyMock())

enableAutoUnmount(afterEach)

const userFixture = {
  id: 'user-1',
  username: 'tester',
  email: 'tester@example.com',
  is_active: true,
  is_superuser: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} satisfies User

const spaceData = {
  used_space: 0,
  max_space: 100,
  available_space: 100,
  utilization_pct: 0,
  stimpack: 0,
  radaway: 0,
}

const lunchboxItem: StorageItemsResponse['items'][number] = {
  id: 'box-1',
  name: 'Lunchbox',
  item_type: 'lunchbox',
  rarity: 'common',
  storage_id: null,
  value: 500,
}

const objectiveFixture: Objective = {
  id: 'objective-1',
  vault_id: 'vault-1',
  challenge: 'Collect a Nuka-Cola',
  progress: 0,
  total: 1,
  reward: '1 Nuka-Cola',
  is_completed: false,
  category: 'daily',
  created_at: '2026-01-01T00:00:00Z',
}

function nukaColaItem(index: number): StorageItemsResponse['items'][number] {
  return {
    id: `nuka-${index}`,
    name: 'Nuka-Cola',
    item_type: 'consumable',
    rarity: 'common',
    storage_id: null,
  }
}

function storageItems(
  nukaCount: number,
  extraItems: StorageItemsResponse['items'] = []
): StorageItemsResponse {
  return {
    weapons: [],
    outfits: [],
    junk: [],
    pets: [],
    items: [...Array.from({ length: nukaCount }, (_, index) => nukaColaItem(index)), ...extraItems],
  }
}

function routeAxiosGets(items: () => StorageItemsResponse): void {
  vi.mocked(axios.get).mockImplementation(async (url: string) => {
    if (url.includes('/items')) return { data: items() }
    if (url.includes('/maintenance')) return { data: { enabled: false } }
    if (url.includes('/space')) return { data: spaceData }
    if (url.includes('/quests/')) return { data: [] }
    return { data: {} }
  })
}

function itemFetchCount(): number {
  return vi.mocked(axios.get).mock.calls.filter(([url]) => String(url).includes('/items')).length
}

/** Mount an observer using the real composable and the app-wide query client. */
function mountHeader(): NukaColaCountState {
  let state: NukaColaCountState | undefined
  const Harness = defineComponent({
    setup() {
      state = useNukaColaCount(ref('vault-1'))
      return () => null
    },
  })
  mountWithSetup(Harness, {}, appQueryClient)
  if (!state) throw new Error('useNukaColaCount did not run during mount')
  return state
}

/** mountWithSetup installs a fresh Pinia, so auth is set after the observer mounts. */
function signInAfterMount(): void {
  const auth = useAuthStore()
  auth.token = 'mock-token'
  auth.user = { ...userFixture }
}

async function clickTab(wrapper: ReturnType<typeof mount>, label: string): Promise<void> {
  // reka-ui TabsTrigger activates on mousedown (left button), not click
  const trigger = wrapper.findAll('button').find((button) => button.text().includes(label))!
  await trigger.trigger('mousedown')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  appQueryClient.clear()
  localStorage.clear()
})

afterEach(() => {
  appQueryClient.clear()
  localStorage.clear()
})

describe('Nuka-Cola reward flows', () => {
  it('refreshes a mounted header after claiming quest rewards', async () => {
    let nukaCount = 1
    routeAxiosGets(() => storageItems(nukaCount))

    const state = mountHeader()
    signInAfterMount()
    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(1))

    nukaCount = 2
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        quest_id: 'quest-1',
        quest_title: 'Quest 1',
        is_completed: true,
        granted_rewards: [],
      },
    })

    await useQuestStore().claimQuestRewards('vault-1', 'quest-1')

    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(2))
    expect(itemFetchCount()).toBeGreaterThanOrEqual(2)
  })

  it('refreshes a mounted header after completing an objective', async () => {
    let nukaCount = 1
    routeAxiosGets(() => storageItems(nukaCount))

    const state = mountHeader()
    signInAfterMount()
    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(1))

    const objectives = useObjectivesStore()
    objectives.objectivesVaultId = 'vault-1'
    objectives.objectives = [objectiveFixture]

    nukaCount = 2
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { progress: 1, total: 1, is_completed: true },
    })

    await objectives.completeObjective('vault-1', 'objective-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/objectives/vault-1/objective-1/claim')
    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(2))
  })

  it('refreshes a mounted header after opening a lunchbox', async () => {
    let nukaCount = 1
    routeAxiosGets(() => storageItems(nukaCount, [lunchboxItem]))

    const pinia = createPinia()
    setActivePinia(pinia)

    // The auth store initializes from storage on creation; seeds come first so
    // it does not trigger a fetchUser() network call.
    localStorage.setItem('token', 'mock-token')
    localStorage.setItem('user', JSON.stringify(userFixture))
    useAuthStore()

    const vaultStore = useVaultStore()
    vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
    vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue(undefined)

    let state: NukaColaCountState | undefined
    const HeaderStorageView = defineComponent({
      setup() {
        state = useNukaColaCount(ref('vault-1'))
        return () => h(StorageView)
      },
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/storage', component: StorageView }],
    })
    await router.push('/vault/vault-1/storage')
    await router.isReady()

    const queryPlugin = {
      install(app: App): void {
        app.use(VueQueryPlugin, { queryClient: appQueryClient })
      },
    }

    const wrapper = mount(HeaderStorageView, {
      global: { plugins: [pinia, queryPlugin, router] },
    })
    if (!state) throw new Error('useNukaColaCount did not run during mount')

    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(1))

    await clickTab(wrapper, 'Supplies')
    wrapper.findComponent({ name: 'StorageItemCard' }).vm.$emit('open')
    await flushPromises()

    const modal = wrapper.findComponent(LunchboxOpenModal)
    expect(modal.props('show')).toBe(true)

    nukaCount = 2
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { items: [], dweller: { name: 'Lucy', rarity: 'rare' } },
    })

    modal.vm.$emit('reveal')

    await vi.waitFor(() => expect(state.nukaColaCount.value).toBe(2))
  })
})
