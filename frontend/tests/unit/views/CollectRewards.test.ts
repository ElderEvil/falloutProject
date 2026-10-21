import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createAxiosMock, createIconifyMock, createRouterMock } from '../helpers/mocks'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { audioManager } from '@/core/audio/audioManager'
import { useToast } from '@/core/composables/useToast'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import ObjectivesView from '@/modules/progression/views/ObjectivesView.vue'
import QuestsView from '@/modules/progression/views/QuestsView.vue'
import type { Objective } from '@/modules/progression/models/objective'
import type { VaultQuest } from '@/modules/progression/models/quest'

vi.mock('@/core/plugins/axios', () => createAxiosMock())
vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' } }))
enableAutoUnmount(afterEach)

let objectives: Objective[]
let quests: VaultQuest[]
const collectButton = '[role="button"][aria-label^="Collect rewards:"]'
const stubs = { SidePanel: true, RouterLink: true }

function objective(id: string, overrides: Partial<Objective> = {}): Objective {
  return {
    id,
    vault_id: 'vault-123',
    challenge: 'Collect caps',
    progress: 100,
    total: 100,
    reward: '50 Caps',
    is_completed: false,
    category: 'daily',
    created_at: '',
    ...overrides,
  }
}

function quest(id: string, overrides: Partial<VaultQuest> = {}): VaultQuest {
  return {
    id,
    title: id,
    short_description: 'Test mission',
    long_description: 'Test mission',
    requirements: '',
    rewards: '50 caps',
    quest_type: 'side',
    quest_category: null,
    chain_id: null,
    chain_order: 0,
    previous_quest_id: null,
    next_quest_id: null,
    created_at: '',
    updated_at: '',
    is_visible: true,
    is_locked: false,
    lock_reason: null,
    is_completed: false,
    is_reward_ready: true,
    started_at: null,
    duration_minutes: null,
    return_started_at: null,
    return_completes_at: null,
    completed_at: null,
    ...overrides,
  }
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.clearAllMocks()
  useToast().toasts.value = []
  vi.spyOn(audioManager, 'play').mockImplementation(() => {})
  objectives = [objective('first'), objective('second', { category: 'weekly' })]
  quests = [quest('first'), quest('second')]
  vi.mocked(axios.get).mockImplementation(async (url) => {
    if (String(url).includes('/objectives/'))
      return { data: objectives.map((item) => ({ ...item })) }
    if (String(url).includes('/quests/')) return { data: quests.map((item) => ({ ...item })) }
    if (String(url).includes('/storage/')) return { data: { items: [] } }
    return { data: [] }
  })
})
afterEach(() => vi.restoreAllMocks())

it('collects earned objectives across tabs and announces the result once', async () => {
  objectives.push(
    objective('pending', { progress: 0 }),
    objective('claimed', { is_completed: true })
  )
  vi.mocked(axios.post).mockImplementation(async (url) => {
    const item = objectives.find((item) => String(url).endsWith(`/${item.id}/claim`))!
    item.is_completed = true
    return { data: { is_completed: true, progress: item.progress, total: item.total } }
  })
  const wrapper = mount(ObjectivesView, { global: { stubs } })
  await flushPromises()
  await wrapper.get(collectButton).trigger('click')
  await flushPromises()
  expect(vi.mocked(axios.post).mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/objectives/vault-123/first/claim',
    '/api/v1/objectives/vault-123/second/claim',
  ])
  expect(useObjectivesStore().objectives.filter((item) => item.is_completed)).toHaveLength(3)
  expect(useToast().toasts.value).toEqual([
    expect.objectContaining({ message: 'Collected 2 rewards', variant: 'success' }),
  ])
  expect(audioManager.play).toHaveBeenCalledExactlyOnceWith('objectiveClaim', 'ui')
})

it('announces collected objectives even if a later claim fails, then retries only unclaimed rewards', async () => {
  vi.mocked(axios.post).mockImplementation(async (url) => {
    if (String(url).includes('/second/')) throw new Error('Claim failed')
    objectives[0]!.is_completed = true
    return { data: { is_completed: true, progress: 100, total: 100 } }
  })
  const wrapper = mount(ObjectivesView, { global: { stubs } })
  await flushPromises()
  await wrapper.get(collectButton).trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Claim failed')
  expect(useToast().toasts.value).toContainEqual(
    expect.objectContaining({ message: 'Collected 1 reward', variant: 'success' })
  )
  expect(audioManager.play).toHaveBeenCalledExactlyOnceWith('objectiveClaim', 'ui')
  vi.mocked(axios.post)
    .mockClear()
    .mockResolvedValue({ data: { is_completed: true, progress: 100, total: 100 } })
  await wrapper.get(collectButton).trigger('click')
  await flushPromises()
  expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/v1/objectives/vault-123/second/claim')
})

it('disables objective collection when no reward is ready', async () => {
  objectives = [objective('pending', { progress: 0 })]
  const wrapper = mount(ObjectivesView, { global: { stubs } })
  await flushPromises()
  expect(wrapper.find('[role="button"][aria-disabled="true"]').exists()).toBe(true)
  await wrapper.find('[role="button"][aria-disabled="true"]').trigger('click')
  expect(axios.post).not.toHaveBeenCalled()
})

it('settles quest claims sequentially and blocks duplicate clicks while pending', async () => {
  useQuestStore().vaultQuests = quests.map((item) => ({ ...item }))
  let finishFirst!: () => void
  vi.mocked(axios.post).mockImplementation(async (url) => {
    if (String(url).includes('/first/'))
      await new Promise<void>((resolve) => {
        finishFirst = resolve
      })
    const item = quests.find((item) => String(url).includes(`/${item.id}/`))!
    item.is_completed = true
    item.is_reward_ready = false
    return { data: { granted_rewards: [{ reward_type: 'caps', amount: 50 }] } }
  })
  const wrapper = mount(QuestsView, { global: { stubs } })
  await flushPromises()
  await wrapper.get(collectButton).trigger('click')
  await flushPromises()
  expect(axios.post).toHaveBeenCalledTimes(1)
  await wrapper.get('[role="button"][aria-disabled="true"]').trigger('click')
  expect(axios.post).toHaveBeenCalledTimes(1)
  finishFirst()
  await flushPromises()
  expect(vi.mocked(axios.post).mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/quests/vault-123/first/claim-rewards',
    '/api/v1/quests/vault-123/second/claim-rewards',
  ])
  expect(useQuestStore().questCategories.readyToClaim).toHaveLength(0)
  expect(useToast().toasts.value).toContainEqual(
    expect.objectContaining({ variant: 'success', message: 'Rewards claimed: 50 caps' })
  )
})

it('keeps quest claim errors visible while continuing to collect other rewards', async () => {
  useQuestStore().vaultQuests = quests.map((item) => ({ ...item }))
  vi.mocked(axios.post).mockImplementation(async (url) => {
    if (String(url).includes('/first/')) throw new Error('Offline')
    quests[1]!.is_completed = true
    quests[1]!.is_reward_ready = false
    return { data: { granted_rewards: [{ reward_type: 'caps', amount: 50 }] } }
  })
  const wrapper = mount(QuestsView, { global: { stubs } })
  await flushPromises()
  await wrapper.get(collectButton).trigger('click')
  await flushPromises()
  expect(useToast().toasts.value).toContainEqual(
    expect.objectContaining({ variant: 'error', message: 'Failed to claim quest rewards' })
  )
  expect(useToast().toasts.value).toContainEqual(
    expect.objectContaining({ variant: 'success', message: 'Rewards claimed: 50 caps' })
  )
  expect(useQuestStore().questCategories.readyToClaim.map((item) => item.id)).toEqual(['first'])
})
