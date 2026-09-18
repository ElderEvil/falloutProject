import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NavBar from '@/modules/vault/components/shell/NavBar.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import type { IncidentTeamMember } from '@/modules/combat/models/incident'
import { audioManager } from '@/core/audio/audioManager'
import type { User } from '@/modules/auth/types/user'

vi.mock('@/core/composables/useVersionDetection', () => ({
  useVersionDetection: () => ({
    versionBadgeVisible: { value: false },
    showChangelog: vi.fn(),
  }),
}))

const testUser: User = {
  id: 'user-1',
  username: 'Overseer',
  email: 'overseer@example.com',
  is_active: true,
  is_superuser: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('NavBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    audioManager.setMuted(true)
    audioManager.setVolume('ui', 0.6)
    audioManager.setVolume('sfx', 0.8)
    audioManager.setVolume('music', 0.4)
  })

  it('uses a terminal-green highlight for user menu items', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: {
          Icon: true,
          NotificationBell: true,
        },
      },
    })

    await wrapper.find('button[aria-label="User menu for Overseer"]').trigger('click')

    const profileItem = wrapper.find('a[aria-label="View profile"]')
    expect(profileItem.classes()).toContain('hover:bg-theme-primary/10')
    expect(profileItem.classes()).toContain('focus:bg-theme-primary/15')
    expect(profileItem.classes()).not.toContain('hover:bg-gray-900')
  })

  it('marks the profile control active on the profile route', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profile', component: { template: '<div />' } }],
    })
    await router.push('/profile')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    expect(wrapper.find('button[aria-label="User menu for Overseer"]').classes()).toContain(
      'bg-theme-primary/10'
    )
  })

  describe('sound toggle', () => {
    async function mountNavBar() {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
      })
      await router.push('/vault/vault-1')
      await router.isReady()

      return mount(NavBar, {
        global: {
          plugins: [router],
          stubs: { Icon: true, NotificationBell: true },
        },
      })
    }

    it('is hidden while no incident is active', async () => {
      const wrapper = await mountNavBar()

      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(false)
      expect(wrapper.find('button[aria-label="Mute sounds"]').exists()).toBe(false)
    })

    it('shows the unmute action while sounds are muted', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']

      const wrapper = await mountNavBar()

      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(true)
    })

    it('mutes and unmutes without leaving the page', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']
      audioManager.setMuted(false)

      const wrapper = await mountNavBar()

      await wrapper.find('button[aria-label="Mute sounds"]').trigger('click')

      expect(audioManager.muted).toBe(true)
      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(true)
    })
  })

  describe('responder chip', () => {
    const teamMember: IncidentTeamMember = {
      id: 'tm-1',
      team_id: 'team-1',
      dweller_id: 'dweller-1',
      slot_number: 1,
      status: 'assigned',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    async function mountNavBar() {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
      })
      await router.push('/vault/vault-1')
      await router.isReady()

      return mount(NavBar, {
        global: {
          plugins: [router],
          stubs: { Icon: true, NotificationBell: true },
        },
      })
    }

    it('is hidden while no incident is active', async () => {
      const wrapper = await mountNavBar()

      expect(wrapper.find('[aria-label*="responders on scene"]').exists()).toBe(false)
    })

    it('shows the total responder count while incidents are active', async () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-1', 'incident-2']
      store.incidentTeams.set('incident-1', [teamMember])
      store.incidentTeams.set('incident-2', [
        { ...teamMember, id: 'tm-2', dweller_id: 'dweller-2' },
        { ...teamMember, id: 'tm-3', dweller_id: 'dweller-3' },
      ])

      const wrapper = await mountNavBar()

      const chip = wrapper.find('[aria-label="3 responders on scene"]')
      expect(chip.exists()).toBe(true)
      expect(chip.text()).toContain('3')
    })

    it('is informational: no glow or hover intent classes', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']

      const wrapper = await mountNavBar()

      const chip = wrapper.find('[aria-label="0 responders on scene"]')
      expect(chip.classes()).toContain('badge-info')
      expect(chip.classes()).not.toContain('badge-live')
      expect(chip.classes()).not.toContain('badge-action')
    })
  })
})
