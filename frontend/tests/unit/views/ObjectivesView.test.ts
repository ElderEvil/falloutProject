import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouterMock } from '../helpers/mocks'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ObjectivesView from '@/modules/progression/views/ObjectivesView.vue'
import ObjectiveCompleteModal from '@/modules/progression/components/ObjectiveCompleteModal.vue'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'
import { audioManager } from '@/core/audio/audioManager'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' } }))

const dailyObjective: Objective = {
  id: 'obj-1',
  vault_id: 'vault-123',
  challenge: 'Collect 100 caps',
  progress: 100,
  total: 100,
  reward: '50 Caps',
  is_completed: false,
  category: 'daily',
  created_at: '',
}

const starterObjective = (sequence: number, completed = false): Objective => ({
  ...dailyObjective,
  id: `starter-${sequence}`,
  category: 'starter',
  sequence,
  challenge: `Starter step ${sequence}`,
  progress: completed ? 1 : 0,
  total: 1,
  is_completed: completed,
  objective_type: 'collect',
})

const officeObjective = (completed = false): Objective => ({
  ...dailyObjective,
  id: 'office',
  category: 'starter',
  sequence: 5,
  challenge: "Build Overseer's Office",
  progress: completed ? 1 : 0,
  total: 1,
  is_completed: completed,
  objective_type: 'build',
  target_entity: { room_type: 'overseers_office' },
})

let wrapper: VueWrapper
let objectivesStore: ReturnType<typeof useObjectivesStore>

function mountView() {
  return mount(ObjectivesView, {
    attachTo: document.body,
    global: {
      stubs: {
        SidePanel: true,
        PageContentRail: { template: '<div><slot /></div>' },
        PageHeader: true,
        Icon: true,
      },
    },
  })
}

// Named slots do not render through the PageHeader stub, so header-level
// assertions mount once with the real header.
function mountWithRealHeader() {
  return mount(ObjectivesView, {
    attachTo: document.body,
    global: {
      stubs: {
        SidePanel: true,
        PageContentRail: { template: '<div><slot /></div>' },
        PageHeader: false,
        Icon: true,
      },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  objectivesStore = useObjectivesStore()
  vi.clearAllMocks()
  vi.spyOn(objectivesStore, 'fetchObjectives').mockResolvedValue()
  document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())
})

afterEach(() => {
  wrapper?.unmount()
})

it('offers an earned starter reward without waiting for earlier steps', async () => {
  objectivesStore.objectives = [starterObjective(0), { ...starterObjective(1), progress: 1 }]
  wrapper = mountView()
  await flushPromises()

  expect(wrapper.text()).not.toContain('Claim earlier starter rewards first.')
  const claimButtons = wrapper.findAll('.claim-btn')
  expect(claimButtons.length).toBe(1)
  expect(claimButtons[0]!.attributes('disabled')).toBeUndefined()
  expect(wrapper.find('[aria-label="1 reward ready to claim"]').exists()).toBe(true)
})

it('puts earned rewards first without changing order within either group or the store', async () => {
  objectivesStore.objectives = [
    { ...dailyObjective, id: 'pending-1', progress: 0 },
    { ...dailyObjective, id: 'ready-1' },
    { ...dailyObjective, id: 'pending-2', progress: 1 },
    { ...dailyObjective, id: 'ready-2' },
    { ...dailyObjective, id: 'claimed', is_completed: true },
  ]
  wrapper = mountView()
  await flushPromises()
  expect(
    wrapper.findAllComponents({ name: 'ObjectiveCard' }).map((card) => card.props('objective').id)
  ).toEqual(['ready-1', 'ready-2', 'pending-1', 'pending-2'])
  expect(objectivesStore.objectives.map(({ id }) => id)).toEqual([
    'pending-1',
    'ready-1',
    'pending-2',
    'ready-2',
    'claimed',
  ])
})

describe('ObjectivesView claim flow', () => {
  it('claiming an objective calls completeObjective and opens the completion modal', async () => {
    const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
    objectivesStore.objectives = [{ ...dailyObjective }]
    const completed = { ...dailyObjective, is_completed: true }
    const completeSpy = vi.spyOn(objectivesStore, 'completeObjective').mockResolvedValue(completed)

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const claimButton = wrapper.find('.claim-btn')
    expect(claimButton.exists()).toBe(true)
    await claimButton.trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(completeSpy).toHaveBeenCalledWith('vault-123', 'obj-1')

    const modal = wrapper.findComponent(ObjectiveCompleteModal)
    expect(modal.exists()).toBe(true)
    expect(modal.props('show')).toBe(true)
    expect(modal.props('objective')).toMatchObject({ id: 'obj-1', reward: '50 Caps' })
    expect(wrapper.text()).toContain('50 Caps')
    expect(play.mock.calls.filter(([key]) => key === 'objectiveClaim')).toEqual([
      ['objectiveClaim', 'ui'],
    ])
    play.mockRestore()
  })

  it('a failed claim surfaces an error toast and opens no modal', async () => {
    const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
    objectivesStore.objectives = [{ ...dailyObjective }]
    vi.spyOn(objectivesStore, 'completeObjective').mockRejectedValue(new Error('Claim failed'))

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    await wrapper.find('.claim-btn').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const modal = wrapper.findComponent(ObjectiveCompleteModal)
    expect(modal.props('show')).toBe(false)
    expect(wrapper.text()).toContain('Claim failed')
    expect(play).not.toHaveBeenCalledWith('objectiveClaim', 'ui')
    play.mockRestore()
  })
})

describe('ObjectivesView collect all', () => {
  it('claims every earned objective from the header button', async () => {
    const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
    objectivesStore.objectives = [
      { ...dailyObjective, id: 'ready-1' },
      { ...dailyObjective, id: 'ready-2', category: 'weekly' },
      { ...dailyObjective, id: 'pending-1', progress: 0 },
      { ...dailyObjective, id: 'claimed-1', is_completed: true },
    ]
    const completeSpy = vi
      .spyOn(objectivesStore, 'completeObjective')
      .mockImplementation(async (_vaultId, objectiveId) => ({
        ...objectivesStore.objectives.find((objective) => objective.id === objectiveId)!,
        is_completed: true,
      }))

    wrapper = mountWithRealHeader()
    await flushPromises()

    const collectAll = wrapper.find('[data-slot="tooltip-trigger"][role="button"]')
    expect(collectAll.attributes('aria-label')).toBe('Collect rewards: 2')
    await collectAll.trigger('click')
    await flushPromises()

    expect(completeSpy.mock.calls.map(([, objectiveId]) => objectiveId)).toEqual([
      'ready-1',
      'ready-2',
    ])
    expect(play.mock.calls.filter(([key]) => key === 'objectiveClaim')).toEqual([
      ['objectiveClaim', 'ui'],
    ])
    expect(wrapper.findComponent(ObjectiveCompleteModal).props('show')).toBe(false)
    play.mockRestore()
  })

  it('disables Collect All when no reward is ready', async () => {
    objectivesStore.objectives = [{ ...dailyObjective, progress: 0 }]

    wrapper = mountWithRealHeader()
    await flushPromises()

    expect(
      wrapper.find('[data-slot="tooltip-trigger"][role="button"]').attributes('aria-disabled')
    ).toBe('true')
  })

  it('stops at the first failed claim and keeps the error visible', async () => {
    vi.spyOn(audioManager, 'play').mockImplementation(() => {})
    objectivesStore.objectives = [
      { ...dailyObjective, id: 'ready-1' },
      { ...dailyObjective, id: 'ready-2' },
    ]
    const completeSpy = vi
      .spyOn(objectivesStore, 'completeObjective')
      .mockResolvedValueOnce({ ...dailyObjective, id: 'ready-1', is_completed: true })
      .mockRejectedValueOnce(new Error('Claim failed'))

    wrapper = mountWithRealHeader()
    await flushPromises()
    await wrapper.find('[data-slot="tooltip-trigger"][role="button"]').trigger('click')
    await flushPromises()

    expect(completeSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Claim failed')
  })
})

describe('ObjectivesView objective gating', () => {
  it('keeps the Starter tab claimable and hides the regular tabs before the Office', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1), challenge: 'Match a dweller to their room' },
      { ...dailyObjective },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(1)
    expect(tabs[0].text()).toContain('Starter')
    expect(wrapper.text()).toContain('Match a dweller to their room')
    expect(wrapper.text()).toContain("claim the Overseer's Office")
    expect(wrapper.text()).not.toContain('Collect 100 caps')
  })

  it('ignores a retired starter when picking the current step', async () => {
    objectivesStore.objectives = [
      starterObjective(5, true),
      {
        ...dailyObjective,
        id: 'retired',
        category: 'starter',
        sequence: null,
        objective_type: undefined,
      },
      { ...dailyObjective, id: 'daily-1' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(5)
    expect(wrapper.text()).toContain('Collect 100 caps')
  })

  it('keeps the tabs locked until the Office is completed', async () => {
    objectivesStore.objectives = [officeObjective(false), { ...dailyObjective }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(1)
    expect(wrapper.text()).not.toContain('Collect 100 caps')
  })

  it('opens the regular tabs once the Office is completed', async () => {
    objectivesStore.objectives = [officeObjective(true), starterObjective(6), { ...dailyObjective }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(5)
    expect(wrapper.text()).toContain('Collect 100 caps')
  })

  it('shows a compact current-step action', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1), challenge: 'Match a dweller to their room' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Match a dweller to their room')
    const action = wrapper.find('.current-step-action')
    expect(action.exists()).toBe(true)
    expect(action.text()).toContain('Open')
  })

  it('keeps the Starter tab after the spotlight is skipped', async () => {
    localStorage.setItem('onboarding:v1', JSON.stringify({ 'vault-123': { skipped: true } }))
    objectivesStore.objectives = [
      { ...starterObjective(1), challenge: 'Match a dweller to their room' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(1)
    expect(tabs[0].text()).toContain('Starter')
    expect(wrapper.text()).toContain('Match a dweller to their room')
  })

  it('claims a starter objective from the Starter tab', async () => {
    const objective = { ...starterObjective(1), progress: 1 }
    objectivesStore.objectives = [objective]
    const completeSpy = vi.spyOn(objectivesStore, 'completeObjective').mockResolvedValue({
      ...objective,
      is_completed: true,
    })

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    await wrapper.find('.claim-btn').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(completeSpy).toHaveBeenCalledWith('vault-123', 'starter-1')
  })
})

describe('ObjectivesView claimable counters', () => {
  it.each([0, 1])(
    'omits hidden daily and weekly rewards until the Office unlock (starter progress %i)',
    async (progress) => {
      objectivesStore.objectives = [
        { ...starterObjective(4), progress },
        officeObjective(),
        { ...dailyObjective },
        { ...dailyObjective, id: 'weekly-1', category: 'weekly' },
      ]
      wrapper = mountWithRealHeader()
      await nextTick()
      const rewardsReady = () => wrapper.findAll('.page-header-metric-value')[0]!.text()

      expect(rewardsReady()).toBe(String(progress))
      expect(
        wrapper
          .findAll('[role="tab"]')
          .map((tab) => tab.text())
          .join(' ')
      ).not.toContain('Daily')

      objectivesStore.objectives[0]!.is_completed = true
      objectivesStore.objectives[1]!.is_completed = true
      await nextTick()

      expect(rewardsReady()).toBe('2')
      expect(
        wrapper
          .findAll('[role="tab"]')
          .map((tab) => tab.text())
          .join(' ')
      ).toContain('Daily')
      expect(wrapper.find('[aria-label="1 reward ready to claim"]').exists()).toBe(true)
    }
  )

  it('counts claimable rewards per tab and omits a tab with none', async () => {
    objectivesStore.objectives = [
      { ...dailyObjective, id: 'daily-1' },
      { ...dailyObjective, id: 'daily-2' },
      { ...dailyObjective, id: 'weekly-1', category: 'weekly' },
      { ...dailyObjective, id: 'daily-pending', progress: 3, total: 10 },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const tabText = (label: string) =>
      wrapper
        .findAll('[role="tab"]')
        .find((tab) => tab.text().startsWith(label))
        ?.text() ?? ''

    expect(tabText('Daily')).toContain('2')
    expect(tabText('Weekly')).toContain('1')
    expect(tabText('Achievement')).not.toMatch(/\d/)
    expect(tabText('Completed')).not.toMatch(/\d/)
  })

  it('does not count an already claimed reward', async () => {
    objectivesStore.objectives = [
      { ...dailyObjective, is_completed: true, progress: 100, total: 100 },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="tab"]').text()).not.toMatch(/\d/)
  })

  it('shows earned rewards without an unfinished-objective total', async () => {
    objectivesStore.objectives = [
      { ...dailyObjective, id: 'daily-1' },
      { ...dailyObjective, id: 'daily-2', progress: 3, total: 10 },
      { ...dailyObjective, id: 'daily-done', is_completed: true },
    ]

    wrapper = mountWithRealHeader()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Open objectives')
    expect(wrapper.text()).toContain('Collect rewards')
  })

  it('offers header help about objectives', async () => {
    objectivesStore.objectives = [{ ...dailyObjective, id: 'daily-1' }]

    wrapper = mountWithRealHeader()
    // PageHelp loads asynchronously on the first header mount of the file, so
    // poll instead of assuming one flush settles the dynamic import.
    await vi.waitFor(() => {
      expect(wrapper.find('button[aria-label="About Objectives"]').exists()).toBe(true)
    })
    await wrapper.get('button[aria-label="About Objectives"]').trigger('click')
    await vi.waitFor(() => {
      const help = [...document.querySelectorAll('[role="dialog"]')].find((dialog) =>
        dialog.textContent?.includes('About Objectives')
      )
      expect(help?.textContent).toContain('Vault-Tec issues new directives')
      expect(help?.textContent).toContain('each collection goal begins fresh')
      expect(help?.textContent).toContain('different dwellers')
      expect(help?.textContent).toContain('even when storage is full')
    })
  })

  it('explains what a tab badge number means', async () => {
    objectivesStore.objectives = [{ ...dailyObjective, id: 'daily-1' }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('[data-slot="badge"]')
    expect(badge.exists()).toBe(true)
    const tip = wrapper.find('span[aria-label]')
    expect(tip.attributes('aria-label')).toBe('1 reward ready to claim')
    const tab = wrapper
      .findAll('[role="tab"]')
      .find((candidate) => candidate.find('[data-slot="badge"]').exists())
    tab?.element.dispatchEvent(new FocusEvent('focus'))
    await nextTick()
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain(
      '1 reward ready to claim'
    )
  })

  it('hides the Starter tab once every starter objective is done', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1, true) },
      { ...dailyObjective, id: 'daily-1' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const labels = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(labels.some((label) => label.startsWith('Starter'))).toBe(false)
    for (const expected of ['Daily', 'Weekly', 'Achievement', 'Completed'])
      expect(labels.some((label) => label.startsWith(expected))).toBe(true)
  })

  it('keeps the Starter tab while a starter objective is still open', async () => {
    objectivesStore.objectives = [
      officeObjective(true),
      { ...starterObjective(6) },
      { ...dailyObjective },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const labels = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(labels.some((label) => label.startsWith('Starter'))).toBe(true)
  })

  it('hides the Starter tab when only retired, unearned starters remain', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1, true) },
      {
        ...dailyObjective,
        id: 'retired-1',
        category: 'starter',
        sequence: null,
        objective_type: undefined,
        progress: 0,
      },
      { ...dailyObjective, id: 'daily-1' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const labels = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(labels.some((label) => label.startsWith('Starter'))).toBe(false)
    expect(labels.length).toBe(4)
  })

  it('keeps the Starter tab for a retired starter with an unclaimed reward', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1, true) },
      {
        ...dailyObjective,
        id: 'retired-1',
        category: 'starter',
        sequence: null,
        objective_type: undefined,
      },
      { ...dailyObjective, id: 'daily-1' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const labels = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(labels.some((label) => label.startsWith('Starter'))).toBe(true)
  })
})
