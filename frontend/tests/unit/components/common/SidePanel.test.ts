import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { nextTick } from 'vue'
import SidePanel from '@/core/components/common/SidePanel.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

// Keep the real module surface (`reactiveOmit` etc. are used by the shadcn
// primitives SidePanel renders) and override only the persisted ref so each
// mount starts expanded and never touches localStorage.
vi.mock('@vueuse/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vueuse/core')>()
  const { ref } = await import('vue')
  return {
    ...actual,
    useLocalStorage: <T>(_key: string, defaultValue: T) => ref<T>(defaultValue),
  }
})

const VAULT_PARAM_ROUTES = [
  '/vault/:id',
  '/vault/:id/dwellers',
  '/vault/:id/exploration',
  '/vault/:id/objectives',
  '/vault/:id/quests',
  '/vault/:id/relationships',
  '/vault/:id/training',
  '/vault/:id/map',
  '/vault/:id/storage',
  '/vault/:id/trading',
]

// jsdom ships no working matchMedia; this stub records VueUse's `change`
// listener so a test can drive the window across the breakpoint.
const stubMatchMedia = (matches: boolean) => {
  const listeners = new Set<(event: { matches: boolean }) => void>()
  const mediaQueryList = {
    matches,
    media: '',
    onchange: null,
    addListener: (listener: (event: { matches: boolean }) => void) => listeners.add(listener),
    removeListener: (listener: (event: { matches: boolean }) => void) => listeners.delete(listener),
    addEventListener: (_type: string, listener: (event: { matches: boolean }) => void) =>
      listeners.add(listener),
    removeEventListener: (_type: string, listener: (event: { matches: boolean }) => void) =>
      listeners.delete(listener),
    dispatchEvent: vi.fn(),
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => {
      mediaQueryList.media = query
      return mediaQueryList
    })
  )
  return {
    setMatches(next: boolean) {
      mediaQueryList.matches = next
      for (const listener of listeners) listener({ matches: next })
    },
  }
}

describe('SidePanel', () => {
  let router: Router
  const wrappers: VueWrapper[] = []

  beforeEach(async () => {
    stubMatchMedia(false)
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        ...VAULT_PARAM_ROUTES.map((path) => ({ path, component: { template: '<div />' } })),
        { path: '/profile', component: { template: '<div />' } },
      ],
    })
    await router.push('/vault/vault-1')
    await router.isReady()
  })

  afterEach(() => {
    for (const wrapper of wrappers.splice(0)) {
      wrapper.unmount()
    }
    vi.unstubAllGlobals()
  })

  const mountPanel = (props: { vaultId?: string } = {}) => {
    const wrapper = mount(SidePanel, {
      props,
      global: { plugins: [router] },
      // Focus assertions need the tree attached to the document.
      attachTo: document.body,
    })
    wrappers.push(wrapper)
    return wrapper
  }

  const linkByLabel = (links: DOMWrapper<Element>[], label: string) => {
    const link = links.find((candidate) => candidate.find('.nav-label').text() === label)
    if (!link) {
      throw new Error(`Expected a nav link labelled "${label}"`)
    }
    return link
  }

  describe('navigation semantics', () => {
    it('renders nav entries as real links with route hrefs', () => {
      const wrapper = mountPanel()
      const links = wrapper.findAll('a.nav-item')

      expect(links).toHaveLength(10)
      expect(linkByLabel(links, 'Overview').attributes('href')).toBe('/vault/vault-1')
      expect(linkByLabel(links, 'Dwellers').attributes('href')).toBe('/vault/vault-1/dwellers')
      expect(linkByLabel(links, 'Trading Post').attributes('href')).toBe('/vault/vault-1/trading')
    })

    it('keeps the collapse toggle a button and coming-soon entries non-interactive', () => {
      const wrapper = mountPanel()

      expect(wrapper.findAll('button')).toHaveLength(1)
      expect(wrapper.find('button.toggle-btn').exists()).toBe(true)

      const locked = wrapper.find('.nav-item.locked')
      expect(locked.exists()).toBe(true)
      expect(locked.element.tagName).toBe('DIV')
      expect(locked.find('a, button').exists()).toBe(false)
    })

    it('marks only the active route link with aria-current="page"', async () => {
      await router.push('/vault/vault-1/dwellers')
      const wrapper = mountPanel()

      const current = wrapper.findAll('a.nav-item[aria-current="page"]')
      expect(current).toHaveLength(1)
      expect(current[0].find('.nav-label').text()).toBe('Dwellers')
      expect(current[0].attributes('aria-current')).toBe('page')
      expect(
        linkByLabel(wrapper.findAll('a.nav-item'), 'Overview').attributes('aria-current')
      ).toBeUndefined()
    })
  })

  describe('number hotkeys', () => {
    const pressNumber = (key: string, init: KeyboardEventInit = {}) => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key, ...init }))
    }

    it('ignores number shortcuts while Ctrl, Meta, or Alt is held', async () => {
      await router.push('/profile')
      mountPanel({ vaultId: 'vault-1' })

      pressNumber('2', { ctrlKey: true })
      pressNumber('2', { metaKey: true })
      pressNumber('2', { altKey: true })
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/profile')
    })

    it('navigates on an unmodified number shortcut', async () => {
      await router.push('/profile')
      mountPanel({ vaultId: 'vault-1' })

      pressNumber('2')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/vault/vault-1/dwellers')
    })

    it('ignores number shortcuts inside editable targets', async () => {
      await router.push('/profile')
      mountPanel({ vaultId: 'vault-1' })

      const input = document.createElement('input')
      const textarea = document.createElement('textarea')
      const editable = document.createElement('div')
      editable.setAttribute('contenteditable', 'true')
      // jsdom does not implement HTMLElement.isContentEditable; browsers set it
      // from the contenteditable attribute.
      Object.defineProperty(editable, 'isContentEditable', { value: true, configurable: true })
      document.body.append(input, textarea, editable)

      try {
        for (const target of [input, textarea, editable]) {
          target.dispatchEvent(new KeyboardEvent('keydown', { key: '3', bubbles: true }))
        }
        await flushPromises()

        expect(router.currentRoute.value.path).toBe('/profile')
      } finally {
        input.remove()
        textarea.remove()
        editable.remove()
      }
    })
  })

  describe('Ctrl/Cmd+B toggle', () => {
    it('still collapses and expands the panel', async () => {
      const wrapper = mountPanel()
      expect(wrapper.find('.side-panel.collapsed').exists()).toBe(false)

      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', code: 'KeyB', ctrlKey: true }))
      await nextTick()
      expect(wrapper.find('.side-panel.collapsed').exists()).toBe(true)

      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', code: 'KeyB', ctrlKey: true }))
      await nextTick()
      expect(wrapper.find('.side-panel.collapsed').exists()).toBe(false)
    })

    it('does not hijack Ctrl+B inside an editable target', async () => {
      const wrapper = mountPanel()
      const input = document.createElement('input')
      document.body.append(input)

      try {
        input.dispatchEvent(
          new KeyboardEvent('keydown', { code: 'KeyB', ctrlKey: true, bubbles: true })
        )
        await nextTick()

        expect(wrapper.find('.side-panel.collapsed').exists()).toBe(false)
      } finally {
        input.remove()
      }
    })
  })

  describe('coming soon copy', () => {
    it('describes the locked entry as Coming soon without a stale roadmap date', async () => {
      const wrapper = mountPanel()
      const locked = wrapper.find('.nav-item.locked')

      await locked.trigger('focus')
      await nextTick()
      await nextTick()

      const bodyText = document.body.textContent ?? ''
      expect(bodyText).toContain('Achievements - Coming soon')
      expect(bodyText).not.toContain('Mar-Apr')
      expect(bodyText).not.toContain('2026')
    })
  })

  describe('mobile drawer', () => {
    it('shows mobile labels after collapsing desktop navigation and preserves desktop collapse', async () => {
      const media = stubMatchMedia(false)
      const wrapper = mountPanel()
      const toggle = wrapper.find('button.toggle-btn')
      await toggle.trigger('click')
      expect(wrapper.find('.nav-label').exists()).toBe(false)

      media.setMatches(true)
      await nextTick()
      await toggle.trigger('click')

      expect(wrapper.findAll('a.nav-item .nav-label')).toHaveLength(10)
      expect(wrapper.find('.locked-label').text()).toBe('Achievements')
      expect(wrapper.find('.nav-divider').exists()).toBe(true)
      expect(wrapper.find('.wip-badge').exists()).toBe(true)
      expect(wrapper.find('.hotkey-badge').exists()).toBe(true)

      media.setMatches(false)
      await nextTick()
      expect(wrapper.find('.nav-label').exists()).toBe(false)
      expect(toggle.attributes('aria-label')).toBe('Expand navigation panel')
    })

    it('tracks the mobile breakpoint reactively for the label, icon, and aria-expanded', async () => {
      const media = stubMatchMedia(false)
      const wrapper = mountPanel()
      const toggle = wrapper.find('button.toggle-btn')

      expect(toggle.attributes('aria-label')).toBe('Collapse navigation panel')
      expect(toggle.find('.icon-mock').attributes('data-icon')).toBe('mdi:chevron-left')
      expect(toggle.attributes('aria-expanded')).toBe('true')

      media.setMatches(true)
      await nextTick()

      expect(toggle.attributes('aria-label')).toBe('Open navigation panel')
      expect(toggle.find('.icon-mock').attributes('data-icon')).toBe('mdi:menu')
      expect(toggle.attributes('aria-expanded')).toBe('false')

      await toggle.trigger('click')
      await nextTick()
      expect(toggle.attributes('aria-expanded')).toBe('true')

      media.setMatches(false)
      await nextTick()

      expect(toggle.attributes('aria-label')).toBe('Collapse navigation panel')
      expect(toggle.find('.icon-mock').attributes('data-icon')).toBe('mdi:chevron-left')
      expect(toggle.attributes('aria-expanded')).toBe('true')
    })

    it('opens and closes via the toggle, moving and returning focus', async () => {
      stubMatchMedia(true)
      const wrapper = mountPanel()
      const toggle = wrapper.find('button.toggle-btn')

      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)
      expect(toggle.attributes('aria-expanded')).toBe('false')
      expect(wrapper.find('.panel-backdrop').exists()).toBe(false)

      await toggle.trigger('click')
      await nextTick()

      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(true)
      expect(toggle.attributes('aria-expanded')).toBe('true')
      expect(wrapper.find('.panel-backdrop').exists()).toBe(true)
      expect(document.activeElement).toBe(wrapper.find('.panel-surface').element)

      await toggle.trigger('click')
      await nextTick()

      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)
      expect(wrapper.find('.panel-backdrop').exists()).toBe(false)
      expect(document.activeElement).toBe(toggle.element)
    })

    it('closes on backdrop click and Escape', async () => {
      stubMatchMedia(true)
      const wrapper = mountPanel()
      const toggle = wrapper.find('button.toggle-btn')

      await toggle.trigger('click')
      await wrapper.find('.panel-backdrop').trigger('click')
      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)

      await toggle.trigger('click')
      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(true)
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await nextTick()
      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)
    })

    it('closes when the route changes', async () => {
      stubMatchMedia(true)
      const wrapper = mountPanel()
      await wrapper.find('button.toggle-btn').trigger('click')
      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(true)

      await router.push('/vault/vault-1/dwellers')
      await flushPromises()

      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)
    })

    it('keeps the desktop collapse behaviour outside the mobile breakpoint', async () => {
      const wrapper = mountPanel()

      await wrapper.find('button.toggle-btn').trigger('click')

      expect(wrapper.find('.side-panel.collapsed').exists()).toBe(true)
      expect(wrapper.find('.side-panel.mobile-open').exists()).toBe(false)
      expect(wrapper.find('button.toggle-btn').attributes('aria-expanded')).toBe('false')
    })
  })

  describe('toggle tooltip', () => {
    const openTooltip = async (wrapper: VueWrapper) => {
      await wrapper.find('button.toggle-btn').trigger('focus')
      await nextTick()
      await nextTick()
      return document.body.textContent ?? ''
    }

    it('keeps the Ctrl+B hint on desktop', async () => {
      const wrapper = mountPanel()

      expect(await openTooltip(wrapper)).toContain('Collapse navigation panel (Ctrl+B)')
    })

    it('omits the Ctrl+B hint on mobile, where the shortcut does not open the drawer', async () => {
      stubMatchMedia(true)
      const wrapper = mountPanel()

      const bodyText = await openTooltip(wrapper)
      expect(bodyText).toContain('Open navigation panel')
      expect(bodyText).not.toContain('Ctrl+B')
    })
  })
})
