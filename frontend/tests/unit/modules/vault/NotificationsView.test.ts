import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock, createIconifyMock } from '../../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import axios from '@/core/plugins/axios'
import NotificationsView from '@/modules/vault/views/NotificationsView.vue'
import { Select } from '@/core/components/ui/select'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useNotificationInboxStore } from '@/modules/vault/stores/notificationInbox'

vi.mock('@/core/plugins/axios', () => createAxiosMock())
vi.mock('@iconify/vue', () => createIconifyMock())

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  useVaultStore().selectedVaultId = 'vault-a'
  vi.mocked(axios.get).mockResolvedValue({ data: [] })
})

async function render(query = '') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', component: NotificationsView },
      { path: '/', component: { template: '<div />' } },
    ],
  })
  await router.push(`/notifications${query}`)
  const wrapper = mount(NotificationsView, {
    global: { plugins: [router], stubs: { SidePanel: true, PageNavigation: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('notification inbox page', () => {
  it('defaults to the current vault and combines the read-status control with that vault', async () => {
    const { wrapper, router } = await render()
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-a', is_read: undefined, offset: 0, limit: 50 },
    })
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Unread')!
      .trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ vault: 'vault-a', status: 'unread' })
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-a', is_read: false, offset: 0, limit: 50 },
    })
    expect(wrapper.text()).toContain('All caught up')
    wrapper.unmount()
  })

  it('supports all vaults and restores filters from the URL', async () => {
    const { wrapper, router } = await render('?vault=all&status=read')
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: undefined, is_read: true, offset: 0, limit: 50 },
    })
    wrapper.findComponent(Select).vm.$emit('update:modelValue', 'vault-b')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ vault: 'vault-b', status: 'read' })
    await router.push('/notifications?vault=all&status=unread')
    await flushPromises()
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: undefined, is_read: false, offset: 0, limit: 50 },
    })
    wrapper.unmount()
  })

  it('allows informational messages to be marked read without a destination', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: [
        {
          id: 'system-1',
          title: 'System update',
          message: 'A message',
          vault_id: null,
          notification_type: 'level_up',
          priority: 'normal',
          is_read: false,
          created_at: '2026-10-24T00:00:00Z',
        },
      ],
    })
    const { wrapper } = await render('?vault=all')
    expect(wrapper.text()).toContain('System update')
    expect(wrapper.text()).not.toContain('View details')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Mark read')!
      .trigger('click')
    await flushPromises()
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/system-1/read', {})
    expect(useNotificationInboxStore().readRevision).toBe(1)
    wrapper.unmount()
  })
})
