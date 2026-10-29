import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from '@/modules/vault/views/HomeView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

describe('HomeView', () => {
  let router: any
  let vaultStore: any

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())

    // Set token and user in localStorage before initializing store
    // so useLocalStorage picks them up and doesn't trigger fetchUser
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'test-user-id',
        username: 'testuser',
        email: 'test@example.com',
      })
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

    // Mock console.error to clean up test output
    vi.spyOn(console, 'error').mockImplementation(() => {})

    vi.clearAllMocks()
    vi.mocked(axios.get).mockImplementation(async (url: string) => {
      if (url === '/api/v1/vaults/scenarios') return { data: [] }
      return { data: [...vaultStore.vaults] }
    })
  })

  const findCreateButton = (wrapper: any) => {
    return wrapper.findAll('button').find((btn: any) => btn.text().includes('Create Vault'))
  }

  const settleView = async () => {
    await flushPromises()
    await vi.dynamicImportSettled()
    await flushPromises()
  }

  const continueStep = async (wrapper: any) => {
    await wrapper.get('form').trigger('submit')
    await settleView()
  }

  const goToReview = async (wrapper: any) => {
    if (wrapper.find('input[type="number"]').exists()) await continueStep(wrapper)
    await continueStep(wrapper)
  }

  const vaultsAtCount = (count: number) =>
    Array.from({ length: count }, (_, index) => ({
      id: `vault-${index + 1}`,
      number: index + 1,
      bottle_caps: 100,
      happiness: 75,
      power: 50,
      power_max: 100,
      food: 50,
      food_max: 100,
      water: 50,
      water_max: 100,
      room_count: 5,
      dweller_count: 10,
      updated_at: new Date().toISOString(),
    }))

  describe('Rendering', () => {
    it('should render welcome message', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      expect(wrapper.text()).toContain('Welcome to Fallout Shelter')
    })

    it('should render create vault form', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      expect(wrapper.find('h2').text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
      expect(wrapper.get('button[type="submit"]').text()).toBe('Continue')
      expect(wrapper.text()).toContain('VAULT-TEC // COMMISSIONING')
    })

    it('keeps the create action compact and high-contrast', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      const continueButton = wrapper.get('button[type="submit"]')
      expect(continueButton.text()).toBe('Continue')
      expect(continueButton.element.tagName).toBe('BUTTON')
      expect(findCreateButton(wrapper)).toBeUndefined()
    })

    it('explains the boosted start and shows the experimental warning once', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      await wrapper.get('input[type="number"]').setValue('123')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Creates an expanded vault')
      expect(wrapper.text()).toContain('an arena')
      expect(wrapper.text()).toContain('caps for upgrades')
      expect(wrapper.text()).toContain('all seven training rooms')
      expect(wrapper.text()).not.toContain('Vaults are experimental')
      await continueStep(wrapper)
      expect(wrapper.text().match(/Vaults are experimental/g)).toHaveLength(1)
    })

    it('opens vault commissioning when no vaults exist', async () => {
      vaultStore.vaults = []

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      expect(wrapper.text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    })

    it('navigates into a newly created vault instead of staying on the list', async () => {
      vaultStore.vaults = []
      vi.mocked(axios.get).mockResolvedValue({ data: [] })
      vi.spyOn(vaultStore, 'createVault').mockResolvedValue('vault-99')

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      await wrapper.get('input[type="number"]').setValue('101')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(vaultStore.createVault).toHaveBeenCalled()
      expect(router.currentRoute.value.path).toBe('/vault/vault-99')
    })

    it('creates the Vault 1 scenario only when opted in', async () => {
      vaultStore.vaults = []
      vi.mocked(axios.get).mockImplementation(async (url: string) => {
        if (url === '/api/v1/vaults/scenarios') {
          return {
            data: [
              {
                number: 1,
                key: 'vault_1_test',
                title: 'Vault 1 — Scout Test',
                description: 'Adds a level 5 / SPECIAL 4 Scout and a single-scene expedition.',
                requires_boosted: false,
                expedition: true,
              },
            ],
          }
        }
        return { data: [] }
      })
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-1' } })

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      await wrapper.get('input[type="number"]').setValue('1')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Vault 1 — Scout Test')
      await wrapper.get('#scenario-start').trigger('click')
      expect(wrapper.get('#scenario-start').attributes('aria-checked')).toBe('true')

      await continueStep(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        {
          number: 1,
          boosted: false,
          vault_mode: 'standard',
          scenario: 'vault_1_test',
        },
        expect.anything()
      )
      expect(router.currentRoute.value.path).toBe('/vault/vault-1')
    })

    it('forces Boosted Start for a scenario that requires it', async () => {
      vaultStore.vaults = []
      vi.mocked(axios.get).mockImplementation(async (url: string) => {
        if (url === '/api/v1/vaults/scenarios') {
          return {
            data: [
              {
                number: 68,
                key: 'vault_68_test',
                title: 'Vault 68 — The Ratio',
                description: '99 men and 1 woman: a Vault-Tec gender-ratio experiment.',
                requires_boosted: true,
                expedition: false,
              },
            ],
          }
        }
        return { data: [] }
      })
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-68' } })

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      await wrapper.get('input[type="number"]').setValue('68')
      await continueStep(wrapper)
      await wrapper.get('#scenario-start').trigger('click')
      await flushPromises()

      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('true')
      await wrapper.get('#boosted-start').trigger('click')
      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('true')

      await continueStep(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        {
          number: 68,
          boosted: true,
          vault_mode: 'standard',
          scenario: 'vault_68_test',
        },
        expect.anything()
      )
    })

    it('should show vault list when vaults exist', async () => {
      vaultStore.vaults = [
        {
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
        },
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.text()).toContain('Vault 101')
      expect(wrapper.text()).not.toContain('Vault Screenshot')
      expect(wrapper.find('[aria-label="Vault 101 terminal"]').exists()).toBe(true)
      expect(wrapper.findAll('[role="progressbar"]')).toHaveLength(3)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('Create another vault')

      await wrapper
        .findAll('button')
        .find((button) => button.text().includes('Create another vault'))!
        .trigger('click')
      await settleView()
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    })

    it('keeps cached vaults available when the refresh fails', async () => {
      vaultStore.vaults = vaultsAtCount(1)
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.text()).toContain('Could not load your vaults')
      expect(wrapper.find('[aria-label="Vault 1 terminal"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
    })

    it('offers an explicit keyboard-accessible action to select a vault', async () => {
      vaultStore.vaults = vaultsAtCount(1)
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      const selectButton = wrapper
        .findAll('button')
        .find((button) => button.text() === 'Select Vault')
      expect(selectButton).toBeDefined()
      await selectButton!.trigger('click')
      expect(wrapper.text()).toContain('Load Vault')
    })

    it('hides creation at three vaults while keeping existing vaults available', async () => {
      vaultStore.vaults = vaultsAtCount(3)

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(3)
      expect(wrapper.find('[data-slot="alert"]').exists()).toBe(false)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Create another vault')
    })

    it('explains the restriction to users who already have more than three vaults', async () => {
      vaultStore.vaults = vaultsAtCount(4)

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(4)
      expect(wrapper.text()).toContain('You have 4 vaults')
      expect(wrapper.text()).toContain('Delete excess vaults to return to the 3-vault limit')
      expect(wrapper.find('[data-slot="alert-title"]').text()).toBe('Vault limit exceeded')
      expect(wrapper.find('[data-slot="alert-description"]').text()).toContain(
        'You can keep using your existing vaults'
      )
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
    })
  })

  describe('Creation focus mode', () => {
    const clickButtonWithText = async (wrapper: any, text: string) => {
      const button = wrapper.findAll('button').find((btn: any) => btn.text().includes(text))
      expect(button, `button "${text}" should exist`).toBeDefined()
      await button!.trigger('click')
      await settleView()
    }

    it('hides the vault list while creating and restores it when creation is hidden', async () => {
      vaultStore.vaults = vaultsAtCount(2)

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(2)

      await clickButtonWithText(wrapper, 'Create another vault')

      expect(wrapper.text()).toContain('Create New Vault')
      expect(wrapper.text()).not.toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(0)

      await clickButtonWithText(wrapper, 'Hide new vault form')

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(2)
    })

    it('shows step guidance at the top of the creation card', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.text()).toContain('Choose an unused vault number (1-999)')
      expect(wrapper.get('[aria-current="step"]').text()).toContain('Vault number')
      expect(wrapper.find('[aria-label="Vault setup progress"]').exists()).toBe(true)
    })

    it('focuses the vault number input when the creation form opens', async () => {
      vaultStore.vaults = vaultsAtCount(1)

      const wrapper = mount(HomeView, {
        attachTo: document.body,
        global: { plugins: [router] },
      })
      await settleView()

      await clickButtonWithText(wrapper, 'Create another vault')
      await settleView()

      expect(document.activeElement).toBe(wrapper.find('input[type="number"]').element)
      wrapper.unmount()
    })
  })

  describe('Vault Number Validation', () => {
    it('should accept valid vault number (1-999)', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = wrapper.get('button[type="submit"]')

      await input.setValue('123')
      await settleView()

      expect(submitBtn!.attributes('disabled')).toBeUndefined()
      expect(wrapper.find('.text-danger').exists()).toBe(false)
    })

    it('should reject negative vault number on submit', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('-1')
      await settleView()

      // Check for validation error
      expect(wrapper.find('.text-danger').exists()).toBe(true)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('should reject vault number above 999 on submit', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await settleView()

      // Check for validation error
      expect(wrapper.find('.text-danger').exists()).toBe(true)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('should accept decimal numbers (parseInt converts to integer)', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('100.5')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      // parseInt converts 100.5 to 100, which is valid
      // This documents current behavior - decimals are truncated
      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 100, boosted: false, vault_mode: 'standard' }, // Not 100.5
        expect.anything()
      )
    })

    it('should show validation error in VaultNumberField without disabling button', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = wrapper.get('button[type="submit"]')

      await input.setValue('1000')
      await settleView()

      // Button stays enabled (validation is checked on click via VaultNumberField)
      expect(submitBtn!.attributes('disabled')).toBeUndefined()
      // Validation error shown inside VaultNumberField
      expect(wrapper.find('.text-danger').exists()).toBe(true)
    })
  })

  describe('Vault Creation', () => {
    it('should create vault with valid number', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 123, boosted: false, vault_mode: 'standard' },
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      )
    })

    it('should show loading state during vault creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      wrapper.get('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(submitBtn!.text()).toContain('Creating...')
      expect(submitBtn!.attributes('disabled')).toBeDefined()
    })

    it('should clear input after successful creation', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('')
    })

    it('keeps commissioning open with the entered number when creation fails', async () => {
      vaultStore.vaults = [
        {
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
        },
      ]
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Vault number is unavailable'))

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()
      await wrapper
        .findAll('button')
        .find((button) => button.text().includes('Create another vault'))!
        .trigger('click')
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(wrapper.text()).toContain('Ready to open the doors?')
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Back')!
        .trigger('click')
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Back')!
        .trigger('click')
      expect((wrapper.find('input[type="number"]').element as HTMLInputElement).value).toBe('123')
    })

    it('should prevent double submission during creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      wrapper.get('form').trigger('submit')
      wrapper.get('form').trigger('submit')
      wrapper.get('form').trigger('submit')
      await settleView()

      // Should only be called once
      expect(axios.post).toHaveBeenCalledTimes(1)
    })

    it('should not submit with invalid vault number', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await settleView()

      const submitBtn = wrapper.get('button[type="submit"]')
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).not.toHaveBeenCalled()
    })
  })

  describe('Vault Mode Selection', () => {
    const findModeToggle = (wrapper: any, label: string) =>
      wrapper.findAll('button').find((button: any) => button.text().includes(label))

    it('defaults to Standard, explains both modes, and warns the choice is irreversible', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      await wrapper.get('input[type="number"]').setValue('123')
      await continueStep(wrapper)
      const standard = findModeToggle(wrapper, 'Standard')
      const survival = findModeToggle(wrapper, 'Survival')
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
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await continueStep(wrapper)
      await findModeToggle(wrapper, 'Survival')!.trigger('click')

      await goToReview(wrapper)
      const submitBtn = findCreateButton(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 123, boosted: false, vault_mode: 'survival' },
        expect.anything()
      )
    })

    it('disables Boosted Start in Survival mode and never posts a boost with survival', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('creation rejected'))
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await continueStep(wrapper)

      // Opt into Boosted Start while Standard is selected.
      await wrapper.find('#boosted-start').trigger('click')
      expect(wrapper.find('#boosted-start').attributes('aria-checked')).toBe('true')
      expect(wrapper.find('#boosted-start').attributes('disabled')).toBeUndefined()

      // Survival disables the control, states the reason, and clears the boost.
      await findModeToggle(wrapper, 'Survival')!.trigger('click')
      expect(wrapper.find('#boosted-start').attributes('disabled')).toBeDefined()
      expect(wrapper.find('#boosted-start').attributes('aria-checked')).toBe('false')
      expect(wrapper.text()).toContain('Not available in Survival mode')
      // The control stays visible with its label and description intact.
      expect(wrapper.find('label[for="boosted-start"]').text()).toContain('Boosted Start')
      expect(wrapper.find('details').text()).toContain('Creates an expanded vault')

      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 123, boosted: false, vault_mode: 'survival' },
        expect.anything()
      )

      // Switching back to Standard re-enables Boosted Start.
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Back')!
        .trigger('click')
      await findModeToggle(wrapper, 'Standard')!.trigger('click')
      expect(wrapper.find('#boosted-start').attributes('disabled')).toBeUndefined()
      expect(wrapper.text()).not.toContain('Not available in Survival mode')
    })
  })

  describe('Commissioning steps', () => {
    it('shows only the current decision and blocks skipping ahead', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()

      expect(wrapper.text()).toContain('Choose your vault number')
      expect(wrapper.find('#boosted-start').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Deaths are permanent')
      expect(findCreateButton(wrapper)).toBeUndefined()
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
      const futureSteps = wrapper.findAll('[aria-label="Vault setup progress"] button').slice(1)
      expect(futureSteps.every((button) => button.attributes('disabled') !== undefined)).toBe(true)
      await wrapper.get('input[type="number"]').setValue('1000')
      await continueStep(wrapper)
      expect(wrapper.text()).toContain('Choose your vault number')
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('retains choices when moving back and creates a boosted standard vault only after review', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()
      await wrapper.get('input[type="number"]').setValue('68')
      await continueStep(wrapper)
      await wrapper.get('#boosted-start').trigger('click')
      await continueStep(wrapper)

      expect(wrapper.text()).toContain('Ready to open the doors?')
      expect(wrapper.text()).toContain('068')
      expect(wrapper.text()).toContain('Boosted Start')
      expect(axios.post).not.toHaveBeenCalled()
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Back')!
        .trigger('click')
      expect(wrapper.get('#boosted-start').attributes('aria-checked')).toBe('true')
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Back')!
        .trigger('click')
      expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('68')
      await goToReview(wrapper)
      await wrapper.get('form').trigger('submit')
      await settleView()
      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 68, boosted: true, vault_mode: 'standard' },
        expect.anything()
      )
    })

    it('retains the reviewed options after an API error and allows retry', async () => {
      vi.mocked(axios.post)
        .mockRejectedValueOnce(new Error('Temporary failure'))
        .mockResolvedValueOnce({ data: { id: 'new-vault' } })
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
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

  describe('Vault Deletion', () => {
    beforeEach(() => {
      vaultStore.vaults = [
        {
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
        },
      ]
    })

    it('should show delete button when vault is selected', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await settleView()

      // Delete button should appear after selecting vault
      expect(wrapper.text()).toContain('Delete')
    })

    it('should ask for confirmation before deleting', async () => {
      global.confirm = vi.fn(() => false)

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await settleView()

      // Find delete button by text content
      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find((btn: any) => btn.text() === 'Delete Vault')

      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await settleView()
        expect(global.confirm).not.toHaveBeenCalled()
        const dialog = wrapper.findComponent({ name: 'TerminalConfirmation' })
        expect(dialog.props('open')).toBe(true)
        dialog.vm.$emit('cancel')
        await settleView()
      }
      expect(axios.delete).not.toHaveBeenCalled()
    })

    it('should delete vault when confirmed', async () => {
      global.confirm = vi.fn(() => true)
      vi.mocked(axios.delete).mockResolvedValueOnce({ data: {} })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await settleView()

      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find((btn: any) => btn.text() === 'Delete Vault')

      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await settleView()

        expect(axios.delete).not.toHaveBeenCalled()
        const dialog = wrapper.findComponent({ name: 'TerminalConfirmation' })
        expect(dialog.props('open')).toBe(true)
        dialog.vm.$emit('confirm')
        await settleView()
        expect(axios.delete).toHaveBeenCalledWith(
          '/api/v1/vaults/vault-1',
          expect.objectContaining({
            headers: expect.objectContaining({
              Authorization: 'Bearer test-token',
            }),
          })
        )
      }
    })
  })

  describe('Vault Navigation', () => {
    it('should navigate to vault view when clicking Load', async () => {
      vaultStore.vaults = [
        {
          id: 'vault-123',
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
        },
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await settleView()

      const buttons = wrapper.findAll('button')
      const loadBtn = buttons.find((btn: any) => btn.text() === 'Load Vault')

      if (loadBtn) {
        await loadBtn.trigger('click')
        await settleView()
        expect(router.currentRoute.value.path).toBe('/vault/vault-123')
      }
    })
  })

  describe('Vault Display', () => {
    it('makes loading the primary action and keeps deletion compact', async () => {
      vaultStore.vaults = [
        {
          id: 'vault-1',
          number: 101,
          bottle_caps: 0,
          happiness: 100,
          power: 0,
          power_max: 100,
          food: 0,
          food_max: 100,
          water: 0,
          water_max: 100,
          room_count: 0,
          dweller_count: 0,
          updated_at: new Date().toISOString(),
        },
      ]
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await settleView()
      await wrapper.find('li').trigger('click')

      const buttons = wrapper.findAll('button')
      const loadIndex = buttons.findIndex((button) => button.text() === 'Load Vault')
      const deleteIndex = buttons.findIndex((button) => button.text() === 'Delete Vault')

      // Load is the primary action: both actions render, Load before Delete.
      expect(loadIndex).toBeGreaterThanOrEqual(0)
      expect(deleteIndex).toBeGreaterThan(loadIndex)
    })

    it('should display vault stats correctly', async () => {
      vaultStore.vaults = [
        {
          id: 'vault-1',
          number: 101,
          bottle_caps: 1500,
          happiness: 85,
          power: 75,
          power_max: 100,
          food: 80,
          food_max: 100,
          water: 90,
          water_max: 100,
          room_count: 8,
          dweller_count: 15,
          updated_at: new Date().toISOString(),
        },
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      expect(wrapper.text()).toContain('Vault 101')
      expect(wrapper.text()).toContain('Caps1500')
      expect(wrapper.text()).toContain('Happiness85%')
      expect(wrapper.text()).toContain('Power75 / 100')
      expect(wrapper.text()).toContain('Food80 / 100')
      expect(wrapper.text()).toContain('Water90 / 100')
      expect(wrapper.text()).toContain('Rooms8')
      expect(wrapper.text()).toContain('Dwellers15')
    })

    it('should sort vaults by last updated', async () => {
      const now = new Date()
      const older = new Date(now.getTime() - 1000000)

      vaultStore.vaults = [
        {
          id: 'vault-1',
          number: 101,
          updated_at: older.toISOString(),
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
        },
        {
          id: 'vault-2',
          number: 102,
          updated_at: now.toISOString(),
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
        },
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await settleView()

      const vaultItems = wrapper.findAll('li')
      // First item should be vault-2 (most recent)
      expect(vaultItems[0].text()).toContain('Vault 102')
    })
  })
})
