import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChangelogModal from '@/modules/profile/components/ChangelogModal.vue'

// Mock @iconify/vue
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>',
  },
}))

// Mock changelogService
vi.mock('@/modules/profile/services/changelogService', () => ({
  changelogService: {
    getChangelog: vi.fn().mockResolvedValue([
      {
        version: '2.9.5',
        date_display: '2026-02-07',
        changes: [
          {
            category: 'Added',
            description: 'New feature',
          },
        ],
      },
    ]),
  },
}))

// Mock FormattedChangeDescription component
vi.mock('@/modules/profile/components/FormattedChangeDescription.vue', () => ({
  default: {
    name: 'FormattedChangeDescription',
    props: ['description'],
    template: '<span>{{ description }}</span>',
  },
}))

describe('ChangelogModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Footer Buttons', () => {
    it('should NOT have "Close" button in footer', async () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: true,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.4',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      await flushPromises()
      expect(wrapper.text()).toContain('New feature')
      expect(wrapper.find('[data-slot="card"]').exists()).toBe(true)
      const buttons = wrapper.findAll('button')
      const closeButton = buttons.find((btn) => btn.text().includes('Close'))
      expect(closeButton).toBeUndefined()
    })

    it('should not show "Got it!" button when there are no new versions', async () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: true,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.5',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      await flushPromises()
      expect(wrapper.text()).toContain('All caught up')
      const buttons = wrapper.findAll('button')
      const gotItButton = buttons.find((btn) => btn.text().includes('Got it!'))
      expect(gotItButton).toBeUndefined()
    })
  })

  describe('Close Behavior', () => {
    it('closes on Escape only while shown', async () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: true,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.4',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(wrapper.emitted('close')).toHaveLength(1)

      await wrapper.setProps({ show: false })
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(wrapper.emitted('close')).toHaveLength(1)
    })

    it('should emit close event when X button is clicked', async () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: true,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.4',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      await wrapper.vm.$nextTick()
      await wrapper.find('[aria-label="Close modal"]').trigger('click')
      expect(wrapper.emitted('close')).toBeTruthy()
    })

    it('should emit only close (not markAsSeen) when backdrop is clicked', async () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: true,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.4',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      await wrapper.vm.$nextTick()
      await wrapper.find('.fixed.inset-0').trigger('click')

      expect(wrapper.emitted('close')).toBeTruthy()
      expect(wrapper.emitted('markAsSeen')).toBeFalsy()
    })
  })

  describe('Rendering', () => {
    it('should not render when show is false', () => {
      const wrapper = mount(ChangelogModal, {
        props: {
          show: false,
          currentVersion: '2.9.5',
          lastSeenVersion: '2.9.4',
        },
        global: {
          stubs: { Teleport: true },
        },
      })

      expect(wrapper.find('[data-slot="card"]').exists()).toBe(false)
    })
  })
})
