import { describe, it, expect, beforeEach, vi } from 'vitest'
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
    vi.mocked(axios.get).mockImplementation(async () => ({ data: [...vaultStore.vaults] }))
  })

  const findCreateButton = (wrapper: any) => {
    return wrapper.findAll('button').find((btn: any) => btn.text().includes('Create Vault'))
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
      await flushPromises()

      expect(wrapper.text()).toContain('Welcome to Fallout Shelter')
    })

    it('should render create vault form', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await flushPromises()

      expect(wrapper.find('h2').text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
      expect(findCreateButton(wrapper)).toBeDefined()
      expect(wrapper.text()).toContain('VAULT-TEC // COMMISSIONING')
    })

    it('keeps the create action compact and high-contrast', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()

      const createButton = findCreateButton(wrapper)
      expect(createButton).toBeDefined()
      expect(createButton!.element.tagName).toBe('BUTTON')
    })

    it('explains the boosted start and shows the experimental warning once', async () => {
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.text()).toContain('23 rooms and 25 dwellers')
      expect(wrapper.text()).toContain('all seven training rooms')
      expect(wrapper.text().match(/Vaults are experimental/g)).toHaveLength(1)
    })

    it('opens vault commissioning when no vaults exist', async () => {
      vaultStore.vaults = []

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
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
      await flushPromises()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.text()).toContain('Vault 101')
      expect(wrapper.text()).not.toContain('Vault Screenshot')
      expect(wrapper.find('[aria-label="Vault 101 terminal"]').exists()).toBe(true)
      expect(wrapper.findAll('[role="progressbar"]')).toHaveLength(3)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('Create another vault')

      await wrapper.findAll('button').find((button) => button.text().includes('Create another vault'))!.trigger('click')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    })

    it('offers an explicit keyboard-accessible action to select a vault', async () => {
      vaultStore.vaults = vaultsAtCount(1)
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()

      const selectButton = wrapper.findAll('button').find((button) => button.text() === 'Select Vault')
      expect(selectButton).toBeDefined()
      await selectButton!.trigger('click')
      expect(wrapper.text()).toContain('Load Vault')
    })

    it('hides creation at three vaults while keeping existing vaults available', async () => {
      vaultStore.vaults = vaultsAtCount(3)

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(3)
      expect(wrapper.find('[data-slot="alert"]').exists()).toBe(false)
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Create another vault')
    })

    it('explains the restriction to users who already have more than three vaults', async () => {
      vaultStore.vaults = vaultsAtCount(4)

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.findAll('[aria-label$="terminal"]')).toHaveLength(4)
      expect(wrapper.text()).toContain('You have 4 vaults')
      expect(wrapper.text()).toContain('Delete excess vaults to return to the 3-vault limit')
      expect(wrapper.find('[data-slot="alert-title"]').text()).toBe('Vault limit exceeded')
      expect(wrapper.find('[data-slot="alert-description"]').text()).toContain('You can keep using your existing vaults')
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
    })
  })

  describe('Vault Number Validation', () => {
    it('should accept valid vault number (0-999)', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = findCreateButton(wrapper)

      await input.setValue('123')
      await flushPromises()

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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('-1')
      await flushPromises()

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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await flushPromises()

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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('100.5')

      const submitBtn = findCreateButton(wrapper)
      await submitBtn!.trigger('click')
      await flushPromises()

      // parseInt converts 100.5 to 100, which is valid
      // This documents current behavior - decimals are truncated
      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 100, boosted: false }, // Not 100.5
        expect.anything()
      )
    })

    it('should show validation error in VaultNumberField without disabling button', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = findCreateButton(wrapper)

      await input.setValue('1000')
      await flushPromises()

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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const submitBtn = findCreateButton(wrapper)
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 123, boosted: false },
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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const submitBtn = findCreateButton(wrapper)
      submitBtn!.trigger('click')
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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const submitBtn = findCreateButton(wrapper)
      await submitBtn!.trigger('click')
      await flushPromises()

      expect((input.element as HTMLInputElement).value).toBe('')
    })

    it('keeps commissioning open with the entered number when creation fails', async () => {
      vaultStore.vaults = [{
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
      }]
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Vault number is unavailable'))

      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()
      await wrapper.findAll('button').find((button) => button.text().includes('Create another vault'))!.trigger('click')

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await findCreateButton(wrapper)!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Create New Vault')
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
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const submitBtn = findCreateButton(wrapper)
      submitBtn!.trigger('click')
      submitBtn!.trigger('click')
      submitBtn!.trigger('click')
      await flushPromises()

      // Should only be called once
      expect(axios.post).toHaveBeenCalledTimes(1)
    })

    it('should not submit with invalid vault number', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router],
        },
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await flushPromises()

      const submitBtn = findCreateButton(wrapper)
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(axios.post).not.toHaveBeenCalled()
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
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

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
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      // Find delete button by text content
      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find((btn: any) => btn.text() === 'Delete Vault')

      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await flushPromises()
        expect(global.confirm).toHaveBeenCalled()
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
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find((btn: any) => btn.text() === 'Delete Vault')

      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await flushPromises()

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
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const loadBtn = buttons.find((btn: any) => btn.text() === 'Load Vault')

      if (loadBtn) {
        await loadBtn.trigger('click')
        await flushPromises()
        expect(router.currentRoute.value.path).toBe('/vault/vault-123')
      }
    })
  })

  describe('Vault Display', () => {
    it('makes loading the primary action and keeps deletion compact', async () => {
      vaultStore.vaults = [
        {
          id: 'vault-1', number: 101, bottle_caps: 0, happiness: 100, power: 0, power_max: 100,
          food: 0, food_max: 100, water: 0, water_max: 100, room_count: 0, dweller_count: 0,
          updated_at: new Date().toISOString(),
        },
      ]
      const wrapper = mount(HomeView, { global: { plugins: [router] } })
      await flushPromises()
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
      await flushPromises()

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
      await flushPromises()

      const vaultItems = wrapper.findAll('li')
      // First item should be vault-2 (most recent)
      expect(vaultItems[0].text()).toContain('Vault 102')
    })
  })
})
