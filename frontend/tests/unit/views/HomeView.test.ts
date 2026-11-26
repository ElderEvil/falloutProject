import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from '@/modules/vault/views/HomeView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useProfileStore } from '@/modules/profile/stores/profile'
import type { UserProfile } from '@/models/profile'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

const vault = (overrides: Record<string, unknown> = {}) => ({
  id: 'vault-1',
  number: 101,
  bottle_caps: 1000,
  happiness: 75,
  power: 50,
  power_max: 100,
  food: 60,
  food_max: 100,
  water: 70,
  water_max: 100,
  room_count: 5,
  dweller_count: 10,
  updated_at: new Date().toISOString(),
  ...overrides,
})

const vaultsAtCount = (count: number) =>
  Array.from({ length: count }, (_, index) =>
    vault({ id: `vault-${index + 1}`, number: index + 1, bottle_caps: 100, food: 50, water: 50 })
  )

const profileWithPreferences = (preferences: Record<string, unknown>): UserProfile => ({
  id: 'profile-1',
  user_id: 'test-user-id',
  bio: null,
  avatar_url: null,
  preferences,
  total_dwellers_created: 0,
  total_caps_earned: 0,
  total_explorations: 0,
  total_rooms_built: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})

const scenario = (overrides: Record<string, unknown> = {}) => ({
  number: 1,
  key: 'vault_1_test',
  title: 'Vault 1 — Wasteland Test',
  description: 'Seeds one named dweller per expedition site.',
  default_boosted: true,
  expedition: true,
  ...overrides,
})

describe('HomeView', () => {
  let router: ReturnType<typeof createRouter>
  let vaultStore: ReturnType<typeof useVaultStore>

  /** Serve the scenario catalogue and the (possibly cached) vault list. */
  const serveApi = (scenarios: Record<string, unknown>[] = []) =>
    vi.mocked(axios.get).mockImplementation(async (url: string) => ({
      data: url === '/api/v1/vaults/scenarios' ? scenarios : [...vaultStore.vaults],
    }))

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())

    // Set token and user in localStorage before initializing store
    // so useLocalStorage picks them up and doesn't trigger fetchUser
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 'test-user-id', username: 'testuser', email: 'test@example.com' })
    )

    useAuthStore()
    vaultStore = useVaultStore()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: HomeView },
        { path: '/vault/:id', component: { template: '<div>Vault</div>' } },
      ],
    })

    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.clearAllMocks()
    serveApi()
  })

  function mountView(options: { attachTo?: HTMLElement; teleportStub?: boolean } = {}) {
    return mount(HomeView, {
      ...(options.attachTo ? { attachTo: options.attachTo } : {}),
      global: {
        plugins: [router],
        ...(options.teleportStub
          ? { stubs: { Teleport: { template: '<div><slot /></div>' } } }
          : {}),
      },
    })
  }

  const settleView = async () => {
    await flushPromises()
    await vi.dynamicImportSettled()
    await flushPromises()
  }

  const buttonWithText = (wrapper: ReturnType<typeof mountView>, text: string) =>
    wrapper.findAll('button').find((button) => button.text().includes(text))

  const clickButton = async (wrapper: ReturnType<typeof mountView>, text: string) => {
    const button = buttonWithText(wrapper, text)
    expect(button, `button "${text}" should exist`).toBeDefined()
    await button!.trigger('click')
    await settleView()
  }

  const continueStep = async (wrapper: ReturnType<typeof mountView>) => {
    await wrapper.get('form').trigger('submit')
    await settleView()
  }

  const goToReview = async (wrapper: ReturnType<typeof mountView>) => {
    if (wrapper.find('input[type="number"]').exists()) await continueStep(wrapper)
    await continueStep(wrapper)
  }

  /** Fill the number, walk to the review step and post the commissioning form. */
  const commission = async (
    wrapper: ReturnType<typeof mountView>,
    number: string,
    { boosted = false, mode }: { boosted?: boolean; mode?: 'Survival' } = {}
  ) => {
    await wrapper.get('input[type="number"]').setValue(number)
    await continueStep(wrapper)
    if (boosted) await wrapper.get('#boosted-start').trigger('click')
    if (mode) await buttonWithText(wrapper, mode)!.trigger('click')
    await goToReview(wrapper)
    await wrapper.get('form').trigger('submit')
    await settleView()
  }

  const modeToggle = (wrapper: ReturnType<typeof mountView>, label: string) =>
    wrapper.findAll('button').find((button) => button.text().includes(label))

  describe('First-run setup', () => {
    it.each([
      ['a new account with no vaults', 0, {}, true],
      [
        'an account that completed setup',
        0,
        { setup: { version: 1, completed: true, skipped: false } },
        false,
      ],
      ['an account that already has a vault', 1, {}, false],
    ])('shows first-run setup only for %s', async (_, count, preferences, shown) => {
      vaultStore.vaults = vaultsAtCount(count) as never
      useProfileStore().profile = profileWithPreferences(preferences)

      const wrapper = mountView({ teleportStub: true })
      await settleView()

      expect(wrapper.text().includes('Welcome, Overseer')).toBe(shown)
      if (shown) expect(wrapper.text()).toContain('Terminal theme')
    })
  })

  describe('Rendering', () => {
    it('welcomes the overseer and opens commissioning when no vaults exist', async () => {
      vaultStore.vaults = []

      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).toContain('Welcome to Fallout Shelter')
      expect(wrapper.text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    })

    it('recommends Standard and shows the first in-vault actions during review', async () => {
      const wrapper = mountView()
      await settleView()

      await wrapper.get('input[type="number"]').setValue('123')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Recommended for your first vault')
      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('false')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('start by checking power, food, and water')
      expect(wrapper.text()).toContain('Open Objectives')
      expect(wrapper.text().match(/Vaults are experimental/g)).toHaveLength(1)
    })

    it('navigates into a newly created vault instead of staying on the list', async () => {
      vaultStore.vaults = []
      vi.spyOn(vaultStore, 'createVault').mockResolvedValue('vault-99')

      const wrapper = mountView()
      await settleView()

      await wrapper.get('input[type="number"]').setValue('101')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(vaultStore.createVault).toHaveBeenCalled()
      expect(router.currentRoute.value.path).toBe('/vault/vault-99')
    })

    it.each([
      [false, 'Standard'],
      [true, 'Standard'],
      [true, 'Survival'],
    ])('handles Vault 1 QA opt-in %s in %s mode', async (enableScenario, mode) => {
      serveApi([scenario()])
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-1' } })
      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).not.toContain('Vault 1 — Wasteland Test')
      await wrapper.get('input[type="number"]').setValue('1')
      await continueStep(wrapper)
      expect(wrapper.get('#scenario-start').attributes('aria-checked')).toBe('false')
      if (mode === 'Survival') await modeToggle(wrapper, mode)!.trigger('click')
      if (enableScenario) await wrapper.get('#scenario-start').trigger('click')

      await continueStep(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 1,
        boosted: enableScenario && mode === 'Standard',
        vault_mode: mode.toLowerCase(),
        ...(enableScenario ? { scenario: 'vault_1_test' } : {}),
      })
    })

    it('shows lore experiments before a number is entered and creates the selected challenge', async () => {
      serveApi([
        scenario({
          number: 69,
          key: 'vault_69_test',
          title: 'Vault 69 — Eight Women, One Man',
          description: 'Start with eight female residents and one male resident.',
          default_boosted: false,
          expedition: false,
        }),
      ])
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-69' } })
      const wrapper = mountView()
      await settleView()

      const experiment = () => buttonWithText(wrapper, 'Vault 69')!
      const back = async () => buttonWithText(wrapper, 'Back')!.trigger('click')

      expect(experiment().exists()).toBe(true)
      await wrapper.get('input[type="number"]').setValue('69')
      await continueStep(wrapper)
      await wrapper.get('#boosted-start').trigger('click')
      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('true')

      await back()
      await experiment().trigger('click')
      expect(wrapper.get('#scenario-start').attributes('aria-checked')).toBe('true')
      expect(wrapper.find('#boosted-start').exists()).toBe(false)
      expect(wrapper.text()).toContain('eight female residents and one male resident')

      await wrapper.get('#scenario-start').trigger('click')
      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('true')
      await wrapper.get('#scenario-start').trigger('click')

      await continueStep(wrapper)
      expect(wrapper.text()).toContain('069')
      expect(wrapper.text()).toContain('Eight Women, One Man')
      expect(wrapper.text()).not.toContain('Boosted Start')
      expect(wrapper.text()).toContain('eight female residents and one male resident')
      expect(axios.post).not.toHaveBeenCalled()
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 69,
        boosted: false,
        vault_mode: 'standard',
        scenario: 'vault_69_test',
      })
      expect(router.currentRoute.value.path).toBe('/vault/vault-69')
    })

    it('shows the vault list when vaults exist', async () => {
      vaultStore.vaults = [vault()] as never

      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.text()).toContain('Vault 101')
      expect(wrapper.text()).not.toContain('Vault Screenshot')
      expect(wrapper.find('[aria-label="Vault 101 terminal"]').exists()).toBe(true)
      expect(wrapper.findAll('[role="progressbar"]')).toHaveLength(3)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('Create another vault')

      await clickButton(wrapper, 'Create another vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    })

    it('keeps cached vaults available when the refresh fails', async () => {
      vaultStore.vaults = vaultsAtCount(1) as never
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).toContain('Could not load your vaults')
      expect(wrapper.find('[aria-label="Vault 1 terminal"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
    })

    it('offers an explicit keyboard-accessible action to select a vault', async () => {
      vaultStore.vaults = vaultsAtCount(1) as never
      const wrapper = mountView()
      await settleView()

      await clickButton(wrapper, 'Select Vault')

      expect(wrapper.text()).toContain('Load Vault')
    })

    it.each([
      [3, false],
      [4, true],
    ])('caps creation at three vaults when %i exist', async (count, exceeded) => {
      vaultStore.vaults = vaultsAtCount(count) as never

      const wrapper = mountView()
      await settleView()

      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(count)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Create another vault')
      if (!exceeded) {
        expect(wrapper.find('[data-slot="alert"]').exists()).toBe(false)
        return
      }
      expect(wrapper.text()).toContain('You have 4 vaults')
      expect(wrapper.text()).toContain('Delete excess vaults to return to the 3-vault limit')
      expect(wrapper.find('[data-slot="alert-title"]').text()).toBe('Vault limit exceeded')
      expect(wrapper.find('[data-slot="alert-description"]').text()).toContain(
        'You can keep using your existing vaults'
      )
    })
  })

  describe('Creation focus mode', () => {
    it('hides the vault list while creating and restores it when creation is hidden', async () => {
      vaultStore.vaults = vaultsAtCount(2) as never

      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(2)

      await clickButton(wrapper, 'Create another vault')

      expect(wrapper.text()).toContain('Create New Vault')
      expect(wrapper.text()).not.toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(0)

      await clickButton(wrapper, 'Hide new vault form')

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(2)
    })

    it('focuses the vault number input when the creation form opens', async () => {
      vaultStore.vaults = vaultsAtCount(1) as never

      const wrapper = mountView({ attachTo: document.body })
      await settleView()

      await clickButton(wrapper, 'Create another vault')

      expect(document.activeElement).toBe(wrapper.find('input[type="number"]').element)
      wrapper.unmount()
    })
  })

  describe('Vault number validation', () => {
    it.each([
      ['123', false],
      ['-1', true],
      ['1000', true],
    ])('validates vault number %s', async (value, invalid) => {
      const wrapper = mountView()
      await settleView()

      await wrapper.get('input[type="number"]').setValue(value)
      await settleView()

      expect(wrapper.find('.text-danger').exists()).toBe(invalid)
      // The button stays enabled: validation is checked inside VaultNumberField.
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
      if (!invalid) return
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('accepts decimal numbers by truncating them', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })

      const wrapper = mountView()
      await settleView()

      await commission(wrapper, '100.5')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 100,
        boosted: false,
        vault_mode: 'standard',
      })
    })
  })

  describe('Vault creation', () => {
    it('creates the vault and clears the input afterwards', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })

      const wrapper = mountView()
      await settleView()

      await commission(wrapper, '123')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 123,
        boosted: false,
        vault_mode: 'standard',
      })
      expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('')
    })

    it('shows the loading state during vault creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mountView()
      await settleView()
      await wrapper.get('input[type="number"]').setValue('123')
      await goToReview(wrapper)

      wrapper.get('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.get('button[type="submit"]').text()).toContain('Creating...')
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    })

    it('keeps commissioning open with the entered number when creation fails', async () => {
      vaultStore.vaults = [vault()] as never
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Vault number is unavailable'))

      const wrapper = mountView()
      await settleView()
      await clickButton(wrapper, 'Create another vault')

      await commission(wrapper, '123')

      expect(wrapper.text()).toContain('Ready to open the doors?')
      await clickButton(wrapper, 'Back')
      await clickButton(wrapper, 'Back')
      expect((wrapper.find('input[type="number"]').element as HTMLInputElement).value).toBe('123')
    })

    it('prevents double submission during creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mountView()
      await settleView()
      await wrapper.get('input[type="number"]').setValue('123')
      await goToReview(wrapper)

      wrapper.get('form').trigger('submit')
      wrapper.get('form').trigger('submit')
      wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledTimes(1)
    })
  })

  describe('Vault mode selection', () => {
    it('defaults to Standard, explains both modes, and warns the choice is irreversible', async () => {
      const wrapper = mountView()
      await settleView()

      await wrapper.get('input[type="number"]').setValue('123')
      await continueStep(wrapper)

      const standard = modeToggle(wrapper, 'Standard')
      const survival = modeToggle(wrapper, 'Survival')
      expect(standard).toBeDefined()
      expect(survival).toBeDefined()
      expect(standard!.attributes('data-state')).toBe('on')
      expect(survival!.attributes('data-state')).toBe('off')
      expect(wrapper.text()).toContain('can be revived with caps')
      expect(wrapper.text()).toContain('Deaths are permanent')
      expect(wrapper.text()).toContain('cannot be changed later')
    })

    it('posts the selected survival mode', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })

      const wrapper = mountView()
      await settleView()

      await commission(wrapper, '123', { mode: 'Survival' })

      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 123,
        boosted: false,
        vault_mode: 'survival',
      })
    })
  })

  describe('Commissioning steps', () => {
    it('creates an ordinary boosted vault after review', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-68' } })
      const wrapper = mountView()
      await settleView()
      await wrapper.get('input[type="number"]').setValue('68')
      await continueStep(wrapper)
      await wrapper.get('#boosted-start').trigger('click')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Boosted Start')
      expect(wrapper.text()).not.toContain('earn your first recruit')
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 68,
        boosted: true,
        vault_mode: 'standard',
      })
    })

    it('shows only the current decision and blocks skipping ahead', async () => {
      const wrapper = mountView()
      await settleView()

      expect(wrapper.text()).toContain('Choose your vault number')
      expect(wrapper.find('#boosted-start').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Deaths are permanent')
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
      const futureSteps = wrapper.findAll('[aria-label="Vault setup progress"] button').slice(1)
      expect(futureSteps.every((button) => button.attributes('disabled') !== undefined)).toBe(true)
      await wrapper.get('input[type="number"]').setValue('1000')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Choose your vault number')
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('retains number and Survival mode when moving back from review', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      const wrapper = mountView()
      await settleView()
      await wrapper.get('input[type="number"]').setValue('68')
      await continueStep(wrapper)
      await modeToggle(wrapper, 'Survival')!.trigger('click')
      await continueStep(wrapper)

      expect(wrapper.text()).toContain('Ready to open the doors?')
      expect(wrapper.text()).toContain('068')
      expect(wrapper.text()).toContain('Deaths are permanent in this vault')
      expect(axios.post).not.toHaveBeenCalled()
      await clickButton(wrapper, 'Back')
      expect(wrapper.text()).toContain('Deaths are permanent')
      await clickButton(wrapper, 'Back')
      expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('68')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 68,
        boosted: false,
        vault_mode: 'survival',
      })
    })

    it('retains the reviewed options after an API error and allows retry', async () => {
      vi.mocked(axios.post)
        .mockRejectedValueOnce(new Error('Temporary failure'))
        .mockResolvedValueOnce({ data: { id: 'new-vault' } })
      const wrapper = mountView()
      await settleView()
      await wrapper.get('input[type="number"]').setValue('69')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(wrapper.text()).toContain('Ready to open the doors?')
      expect(wrapper.text()).toContain('069')
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(axios.post).toHaveBeenCalledTimes(2)
      expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('')
    })
  })

  describe('Vault deletion', () => {
    beforeEach(() => {
      vaultStore.vaults = [vault()] as never
    })

    it('asks for confirmation before deleting', async () => {
      global.confirm = vi.fn(() => false)

      const wrapper = mountView()
      await settleView()
      await wrapper.find('li').trigger('click')
      await settleView()

      expect(wrapper.text()).toContain('Delete')
      await clickButton(wrapper, 'Delete Vault')

      expect(global.confirm).not.toHaveBeenCalled()
      const dialog = wrapper.findComponent({ name: 'TerminalConfirmation' })
      expect(dialog.props('open')).toBe(true)
      dialog.vm.$emit('cancel')
      await settleView()
      expect(axios.delete).not.toHaveBeenCalled()
    })

    it('deletes the vault when confirmed', async () => {
      global.confirm = vi.fn(() => true)
      vi.mocked(axios.delete).mockResolvedValueOnce({ data: {} })

      const wrapper = mountView()
      await settleView()
      await wrapper.find('li').trigger('click')
      await settleView()
      await clickButton(wrapper, 'Delete Vault')

      expect(axios.delete).not.toHaveBeenCalled()
      const dialog = wrapper.findComponent({ name: 'TerminalConfirmation' })
      expect(dialog.props('open')).toBe(true)
      dialog.vm.$emit('confirm')
      await settleView()
      expect(axios.delete).toHaveBeenCalledWith('/api/v1/vaults/vault-1')
    })
  })

  describe('Vault navigation and display', () => {
    it('navigates to the vault view when clicking Load', async () => {
      vaultStore.vaults = [vault({ id: 'vault-123' })] as never

      const wrapper = mountView()
      await settleView()
      await wrapper.find('li').trigger('click')
      await settleView()

      await clickButton(wrapper, 'Load Vault')

      expect(router.currentRoute.value.path).toBe('/vault/vault-123')
    })

    it('displays vault stats correctly', async () => {
      vaultStore.vaults = [
        vault({
          bottle_caps: 1500,
          happiness: 85,
          power: 75,
          food: 80,
          water: 90,
          room_count: 8,
          dweller_count: 15,
        }),
      ] as never

      const wrapper = mountView()
      await settleView()

      const text = wrapper.text()
      expect(text).toContain('Vault 101')
      expect(text).toContain('Caps1500')
      expect(text).toContain('Happiness85%')
      expect(text).toContain('Power75 / 100')
      expect(text).toContain('Food80 / 100')
      expect(text).toContain('Water90 / 100')
      expect(text).toContain('Rooms8')
      expect(text).toContain('Dwellers15')
    })

    it('sorts vaults by last updated', async () => {
      const now = new Date()
      vaultStore.vaults = [
        vault({
          id: 'vault-1',
          number: 101,
          updated_at: new Date(now.getTime() - 1000000).toISOString(),
        }),
        vault({ id: 'vault-2', number: 102, updated_at: now.toISOString() }),
      ] as never

      const wrapper = mountView()
      await settleView()

      expect(wrapper.findAll('li')[0]!.text()).toContain('Vault 102')
    })
  })
})
