import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SidePanel from '@/core/components/common/SidePanel.vue'

vi.mock('@vueuse/core', () => ({
  useLocalStorage: <T>(_key: string, defaultValue: T) => {
    const { ref } = require('vue')
    return ref<T>(defaultValue)
  },
}))

describe('SidePanel', () => {
  let router: any
  let pinia: ReturnType<typeof createPinia>

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id', component: { template: '<div>Vault</div>' } },
        { path: '/vault/:id/dwellers', component: { template: '<div>Dwellers</div>' } },
        { path: '/vault/:id/exploration', component: { template: '<div>Exploration</div>' } },
        { path: '/vault/:id/objectives', component: { template: '<div>Objectives</div>' } },
        { path: '/vault/:id/quests', component: { template: '<div>Quests</div>' } },
        { path: '/vault/:id/relationships', component: { template: '<div>Relationships</div>' } },
        { path: '/vault/:id/training', component: { template: '<div>Training</div>' } },
        { path: '/vault/:id/happiness', component: { template: '<div>Happiness</div>' } },
        { path: '/vault/:id/storage', component: { template: '<div>Storage</div>' } },
        { path: '/vault/:id/map', component: { template: '<div>Map</div>' } },
        { path: '/vault/:id/radio', component: { template: '<div>Radio</div>' } },
        { path: '/profile', component: { template: '<div>Profile</div>' } },
      ],
    })

    await router.push('/vault/vault-1')
  })

  it('uses a labelled navigation landmark', () => {
    const wrapper = mount(SidePanel, { global: { plugins: [router, pinia] } })

    expect(wrapper.find('nav.side-panel').attributes('aria-label')).toBe('Game navigation panel')
  })

  describe('navItems', () => {
    it('keeps vault shortcuts 1–9 available on the profile route', async () => {
      await router.push('/profile')
      const wrapper = mount(SidePanel, {
        props: { vaultId: 'vault-1' },
        global: { plugins: [router, pinia] },
      })

      const hotkeys = wrapper.findAll('.hotkey-badge').map((badge) => badge.text())

      expect(hotkeys).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
    })

    it('marks only the most-specific vault route as active', async () => {
      await router.push('/vault/vault-1/dwellers')
      const wrapper = mount(SidePanel, { global: { plugins: [router, pinia] } })

      expect(wrapper.findAll('.nav-item.active')).toHaveLength(1)
      expect(wrapper.find('.nav-item.active .nav-label').text()).toBe('Dwellers')
    })

    it('should not include a Happiness nav item', async () => {
      await router.isReady()
      const wrapper = mount(SidePanel, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      const navButtons = wrapper.findAll('.nav-item')
      const labels = navButtons.map((b) => b.find('.nav-label')?.text())
      expect(labels).not.toContain('Happiness')
    })

    it('should show Map with hotkey 8', async () => {
      await router.isReady()
      const wrapper = mount(SidePanel, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      const navButtons = wrapper.findAll('.nav-item')
      const mapButton = navButtons.find((b) => b.find('.nav-label')?.text() === 'Map')
      expect(mapButton).toBeTruthy()

      const hotkeyBadge = mapButton!.find('.hotkey-badge')
      expect(hotkeyBadge.exists()).toBe(true)
      expect(hotkeyBadge.text()).toBe('8')
    })

    it('should show hotkey badges for items 1-9', async () => {
      await router.isReady()
      const wrapper = mount(SidePanel, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      const hotkeyBadges = wrapper.findAll('.hotkey-badge')
      const hotkeys = hotkeyBadges.map((b) => b.text())
      expect(hotkeys).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
    })
  })
})
