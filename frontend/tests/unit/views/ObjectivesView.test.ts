import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createRouterMock } from '../helpers/mocks'
import { mount, type VueWrapper, flushPromises } from '@vue/test-utils'
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

/** A daily/weekly reward plus any overrides. */
const objective = (overrides: Partial<Objective> = {}): Objective => ({
  ...dailyObjective,
  ...overrides,
})

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

const retiredStarter = (overrides: Partial<Objective> = {}): Objective => ({
  ...dailyObjective,
  id: 'retired',
  category: 'starter',
  sequence: null,
  objective_type: undefined,
  ...overrides,
})

describe('ObjectivesView', () => {
  let wrapper: VueWrapper
  let objectivesStore: ReturnType<typeof useObjectivesStore>

  function mountView(realHeader = false) {
    return mount(ObjectivesView, {
      attachTo: document.body,
      global: {
        stubs: {
          SidePanel: true,
          PageContentRail: { template: '<div><slot /></div>' },
          // Named slots do not render through the PageHeader stub, so header-level
          // assertions mount once with the real header.
          PageHeader: realHeader ? false : true,
          Icon: true,
        },
      },
    })
  }

  /** Mount, wait for the store read, and let the derived tabs settle. */
  async function mountAndSettle(realHeader = false) {
    wrapper = mountView(realHeader)
    await flushPromises()
    await nextTick()
    return wrapper
  }

  const tabLabels = () => wrapper.findAll('[role="tab"]').map((tab) => tab.text())
  const tabText = (label: string) =>
    wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text().startsWith(label))
      ?.text() ?? ''
  const collectAllButton = () => wrapper.find('[data-slot="tooltip-trigger"][role="button"]')

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
    await mountAndSettle()

    expect(wrapper.text()).not.toContain('Claim earlier starter rewards first.')
    const claimButtons = wrapper.findAll('.claim-btn')
    expect(claimButtons.length).toBe(1)
    expect(claimButtons[0]!.attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[aria-label="1 reward ready to claim"]').exists()).toBe(true)
  })

  it('puts earned rewards first without changing order within either group or the store', async () => {
    objectivesStore.objectives = [
      objective({ id: 'pending-1', progress: 0 }),
      objective({ id: 'ready-1' }),
      objective({ id: 'pending-2', progress: 1 }),
      objective({ id: 'ready-2' }),
      objective({ id: 'claimed', is_completed: true }),
    ]
    await mountAndSettle()

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

  describe('Claim flow', () => {
    it('claiming an objective calls completeObjective and opens the completion modal', async () => {
      const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
      objectivesStore.objectives = [objective()]
      const completeSpy = vi
        .spyOn(objectivesStore, 'completeObjective')
        .mockResolvedValue({ ...dailyObjective, is_completed: true })

      await mountAndSettle()
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
      objectivesStore.objectives = [objective()]
      vi.spyOn(objectivesStore, 'completeObjective').mockRejectedValue(new Error('Claim failed'))

      await mountAndSettle()
      await wrapper.find('.claim-btn').trigger('click')
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()

      expect(wrapper.findComponent(ObjectiveCompleteModal).props('show')).toBe(false)
      expect(wrapper.text()).toContain('Claim failed')
      expect(play).not.toHaveBeenCalledWith('objectiveClaim', 'ui')
      play.mockRestore()
    })

    it('claims a starter objective from the Starter tab', async () => {
      const starter = { ...starterObjective(1), progress: 1 }
      objectivesStore.objectives = [starter]
      const completeSpy = vi
        .spyOn(objectivesStore, 'completeObjective')
        .mockResolvedValue({ ...starter, is_completed: true })

      await mountAndSettle()
      await wrapper.find('.claim-btn').trigger('click')
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()

      expect(completeSpy).toHaveBeenCalledWith('vault-123', 'starter-1')
    })
  })

  describe('Collect all', () => {
    it('claims every earned objective from the header button', async () => {
      const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
      objectivesStore.objectives = [
        objective({ id: 'ready-1' }),
        objective({ id: 'ready-2', category: 'weekly' }),
        objective({ id: 'pending-1', progress: 0 }),
        objective({ id: 'claimed-1', is_completed: true }),
      ]
      const completeSpy = vi
        .spyOn(objectivesStore, 'completeObjective')
        .mockImplementation(async (_vaultId, objectiveId) => ({
          ...objectivesStore.objectives.find((entry) => entry.id === objectiveId)!,
          is_completed: true,
        }))

      await mountAndSettle(true)

      const collectAll = collectAllButton()
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
      objectivesStore.objectives = [objective({ progress: 0 })]

      await mountAndSettle(true)

      expect(collectAllButton().attributes('aria-disabled')).toBe('true')
    })

    it('stops at the first failed claim and keeps the error visible', async () => {
      vi.spyOn(audioManager, 'play').mockImplementation(() => {})
      objectivesStore.objectives = [objective({ id: 'ready-1' }), objective({ id: 'ready-2' })]
      const completeSpy = vi
        .spyOn(objectivesStore, 'completeObjective')
        .mockResolvedValueOnce({ ...dailyObjective, id: 'ready-1', is_completed: true })
        .mockRejectedValueOnce(new Error('Claim failed'))

      await mountAndSettle(true)
      await collectAllButton().trigger('click')
      await flushPromises()

      expect(completeSpy).toHaveBeenCalledTimes(2)
      expect(wrapper.text()).toContain('Claim failed')
    })
  })

  describe('Objective gating', () => {
    it('keeps the Starter tab claimable and hides the regular tabs before the Office', async () => {
      objectivesStore.objectives = [
        { ...starterObjective(1), challenge: 'Match a dweller to their room' },
        objective(),
      ]

      await mountAndSettle()

      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs.length).toBe(1)
      expect(tabs[0]!.text()).toContain('Starter')
      expect(wrapper.text()).toContain('Match a dweller to their room')
      expect(wrapper.text()).toContain("claim the Overseer's Office")
      expect(wrapper.text()).not.toContain('Collect 100 caps')
    })

    it('ignores a retired starter when picking the current step', async () => {
      objectivesStore.objectives = [
        starterObjective(5, true),
        retiredStarter(),
        objective({ id: 'daily-1' }),
      ]

      await mountAndSettle()

      expect(wrapper.findAll('[role="tab"]').length).toBe(5)
      expect(wrapper.text()).toContain('Collect 100 caps')
    })

    it('opens the regular tabs only once the Office is completed', async () => {
      objectivesStore.objectives = [officeObjective(false), objective()]
      await mountAndSettle()

      expect(wrapper.findAll('[role="tab"]').length).toBe(1)
      expect(wrapper.text()).not.toContain('Collect 100 caps')

      wrapper.unmount()
      objectivesStore.objectives = [officeObjective(true), starterObjective(6), objective()]
      await mountAndSettle()

      expect(wrapper.findAll('[role="tab"]').length).toBe(5)
      expect(wrapper.text()).toContain('Collect 100 caps')
    })

    it('keeps the tab icons monochrome', async () => {
      objectivesStore.objectives = [officeObjective(true), starterObjective(6), objective()]
      await mountAndSettle()

      const icons = wrapper.findAll('[role="tab"] svg')
      expect(icons.length).toBeGreaterThan(0)
      for (const icon of icons) {
        expect(icon.attributes('style') ?? '').not.toContain('color')
      }
    })

    it('shows a compact current-step action', async () => {
      objectivesStore.objectives = [
        { ...starterObjective(1), challenge: 'Match a dweller to their room' },
      ]

      await mountAndSettle()

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

      await mountAndSettle()

      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs.length).toBe(1)
      expect(tabs[0]!.text()).toContain('Starter')
      expect(wrapper.text()).toContain('Match a dweller to their room')
    })
  })

  describe('Claimable counters', () => {
    it.each([0, 1])(
      'omits hidden daily and weekly rewards until the Office unlock (starter progress %i)',
      async (progress) => {
        objectivesStore.objectives = [
          { ...starterObjective(4), progress },
          officeObjective(),
          objective(),
          objective({ id: 'weekly-1', category: 'weekly' }),
        ]
        await mountAndSettle(true)
        const rewardsReady = () => wrapper.findAll('.page-header-metric-value')[0]!.text()

        expect(rewardsReady()).toBe(String(progress))
        expect(tabLabels().join(' ')).not.toContain('Daily')

        objectivesStore.objectives[0]!.is_completed = true
        objectivesStore.objectives[1]!.is_completed = true
        await nextTick()

        expect(rewardsReady()).toBe('2')
        expect(tabLabels().join(' ')).toContain('Daily')
        expect(wrapper.find('[aria-label="1 reward ready to claim"]').exists()).toBe(true)
      }
    )

    it('counts claimable rewards per tab and omits a tab with none', async () => {
      objectivesStore.objectives = [
        objective({ id: 'daily-1' }),
        objective({ id: 'daily-2' }),
        objective({ id: 'weekly-1', category: 'weekly' }),
        objective({ id: 'daily-pending', progress: 3, total: 10 }),
      ]

      await mountAndSettle()

      expect(tabText('Daily')).toContain('2')
      expect(tabText('Weekly')).toContain('1')
      expect(tabText('Achievement')).not.toMatch(/\d/)
      expect(tabText('Completed')).not.toMatch(/\d/)
    })

    it('does not count an already claimed reward', async () => {
      objectivesStore.objectives = [objective({ is_completed: true, progress: 100, total: 100 })]

      await mountAndSettle()

      expect(wrapper.find('[role="tab"]').text()).not.toMatch(/\d/)
    })

    it('shows earned rewards without an unfinished-objective total', async () => {
      objectivesStore.objectives = [
        objective({ id: 'daily-1' }),
        objective({ id: 'daily-2', progress: 3, total: 10 }),
        objective({ id: 'daily-done', is_completed: true }),
      ]

      await mountAndSettle(true)

      expect(wrapper.text()).not.toContain('Open objectives')
      expect(wrapper.text()).toContain('Collect rewards')
    })

    it('offers header help about objectives', async () => {
      objectivesStore.objectives = [objective({ id: 'daily-1' })]

      wrapper = mountView(true)
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
      objectivesStore.objectives = [objective({ id: 'daily-1' })]

      await mountAndSettle()

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

    it.each([
      [
        'every starter objective is done',
        () => [starterObjective(1, true), objective({ id: 'daily-1' })],
        false,
        4,
      ],
      [
        'only retired, unearned starters remain',
        () => [
          starterObjective(1, true),
          retiredStarter({ progress: 0 }),
          objective({ id: 'daily-1' }),
        ],
        false,
        4,
      ],
      [
        'a starter objective is still open',
        () => [officeObjective(true), starterObjective(6), objective()],
        true,
        5,
      ],
      [
        'a retired starter still has an unclaimed reward',
        () => [starterObjective(1, true), retiredStarter(), objective({ id: 'daily-1' })],
        true,
        5,
      ],
    ])('shows the Starter tab only when %s', async (_, build, shown, tabCount) => {
      objectivesStore.objectives = build() as Objective[]

      await mountAndSettle()

      const labels = tabLabels()
      expect(labels.some((label) => label.startsWith('Starter'))).toBe(shown)
      expect(labels.length).toBe(tabCount)
      if (!shown) {
        for (const expected of ['Daily', 'Weekly', 'Achievement', 'Completed'])
          expect(labels.some((label) => label.startsWith(expected))).toBe(true)
      }
    })
  })
})
