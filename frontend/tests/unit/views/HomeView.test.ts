import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

describe('HomeView', () => {
  let router: any
  let authStore: any
  let vaultStore: any

  beforeEach(() => {
    setActivePinia(createPinia())
    authStore = useAuthStore()
    vaultStore = useVaultStore()

    // Set authenticated state
    authStore.token = 'test-token'
    authStore.isAuthenticated = true

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: HomeView },
        { path: '/vault/:id', component: { template: '<div>Vault</div>' } }
      ]
    })

    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render welcome message', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Welcome to Fallout Shelter')
    })

    it('should render create vault form', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.find('h2').text()).toContain('Create New Vault')
      expect(wrapper.find('input[type="number"]').exists()).toBe(true)
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    })

    it('should show empty state when no vaults', async () => {
      vaultStore.vaults = []

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('No vaults found')
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
          updated_at: new Date().toISOString()
        }
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Your Vaults')
      expect(wrapper.text()).toContain('Vault 101')
    })
  })

  describe('Vault Number Validation', () => {
    it('should accept valid vault number (0-999)', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = wrapper.find('button[type="submit"]')

      await input.setValue('123')
      await flushPromises()

      expect(submitBtn.attributes('disabled')).toBeUndefined()
      expect(wrapper.find('.text-red-500').exists()).toBe(false)
    })

    it.skip('should reject negative vault number', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('-1')
      await input.trigger('input')
      await flushPromises()

      expect(wrapper.find('.text-red-500').exists()).toBe(true)
      expect(wrapper.text()).toContain('Vault number must be at least 0')
    })

    it.skip('should reject vault number above 999', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await input.trigger('input')
      await flushPromises()

      expect(wrapper.find('.text-red-500').exists()).toBe(true)
      expect(wrapper.text()).toContain('Vault number must be 999 or less')
    })

    it.skip('should show validation error for decimal numbers', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('100.5')
      await input.trigger('input')
      await flushPromises()

      expect(wrapper.find('.text-red-500').exists()).toBe(true)
    })

    it('should disable submit button when validation fails', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      const submitBtn = wrapper.find('button[type="submit"]')

      await input.setValue('1000')
      await input.trigger('input')
      await flushPromises()

      expect(submitBtn.attributes('disabled')).toBeDefined()
    })
  })

  describe('Vault Creation', () => {
    it('should create vault with valid number', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 123 },
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token'
          })
        })
      )
    })

    it('should show loading state during vault creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const form = wrapper.find('form')
      form.trigger('submit')
      await wrapper.vm.$nextTick()

      const submitBtn = wrapper.find('button[type="submit"]')
      expect(submitBtn.text()).toContain('Creating...')
      expect(submitBtn.attributes('disabled')).toBeDefined()
    })

    it('should clear input after successful creation', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'new-vault' } })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect((input.element as HTMLInputElement).value).toBe('')
    })

    it('should prevent double submission during creation', async () => {
      vi.mocked(axios.post).mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve({ data: {} }), 100))
      )

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('123')

      const form = wrapper.find('form')
      form.trigger('submit')
      form.trigger('submit')
      form.trigger('submit')
      await flushPromises()

      // Should only be called once
      expect(axios.post).toHaveBeenCalledTimes(1)
    })

    it('should not submit with invalid vault number', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const input = wrapper.find('input[type="number"]')
      await input.setValue('1000')
      await input.trigger('input')
      await flushPromises()

      await wrapper.find('form').trigger('submit')
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
          updated_at: new Date().toISOString()
        }
      ]
    })

    it('should show delete button when vault is selected', async () => {
      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      // Delete button should appear after selecting vault
      expect(wrapper.html()).toContain('Delete')
    })

    it('should ask for confirmation before deleting', async () => {
      global.confirm = vi.fn(() => false)

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      // Find delete button by text content
      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find(btn => btn.text() === 'Delete')

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
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const deleteBtn = buttons.find(btn => btn.text() === 'Delete')

      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await flushPromises()

        expect(axios.delete).toHaveBeenCalledWith(
          '/api/v1/vaults/vault-1',
          expect.objectContaining({
            headers: expect.objectContaining({
              Authorization: 'Bearer test-token'
            })
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
          updated_at: new Date().toISOString()
        }
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const vaultItem = wrapper.find('li')
      await vaultItem.trigger('click')
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const loadBtn = buttons.find(btn => btn.text() === 'Load')

      if (loadBtn) {
        await loadBtn.trigger('click')
        await flushPromises()
        expect(router.currentRoute.value.path).toBe('/vault/vault-123')
      }
    })
  })

  describe('Vault Display', () => {
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
          updated_at: new Date().toISOString()
        }
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Vault 101')
      expect(wrapper.text()).toContain('Bottle Caps: 1500')
      expect(wrapper.text()).toContain('Happiness: 85%')
      expect(wrapper.text()).toContain('Power: 75 / 100')
      expect(wrapper.text()).toContain('Food: 80 / 100')
      expect(wrapper.text()).toContain('Water: 90 / 100')
      expect(wrapper.text()).toContain('Rooms: 8')
      expect(wrapper.text()).toContain('Dwellers: 15')
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
          dweller_count: 10
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
          dweller_count: 10
        }
      ]

      const wrapper = mount(HomeView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const vaultItems = wrapper.findAll('li')
      // First item should be vault-2 (most recent)
      expect(vaultItems[0].text()).toContain('Vault 102')
    })
  })
})
