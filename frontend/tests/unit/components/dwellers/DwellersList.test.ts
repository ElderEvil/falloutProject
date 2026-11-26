import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { reactive, nextTick } from 'vue'
import { shallowMount, mount } from '@vue/test-utils'
import DwellersList from '@/modules/dwellers/components/DwellersList.vue'
import { makeDweller } from '../../helpers/dwellerFixtures'

const dweller = makeDweller

type ListProps = InstanceType<typeof DwellersList>['$props']

const listProps = (overrides: Partial<ListProps> = {}): Partial<ListProps> => ({
  dwellers: [],
  isLoading: false,
  rooms: [],
  viewMode: 'list',
  ...overrides,
})

/** Minimal IntersectionObserver stand-in: the component under test decides *when* to observe. */
class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = []
  elements = new Set<Element>()

  constructor(
    private readonly callback: (entries: { isIntersecting: boolean }[]) => void,
    readonly options?: IntersectionObserverInit
  ) {
    FakeIntersectionObserver.instances.push(this)
  }

  observe(el: Element) {
    this.elements.add(el)
  }

  unobserve(el: Element) {
    this.elements.delete(el)
  }

  disconnect() {
    this.elements.clear()
  }

  intersect(isIntersecting = true) {
    this.callback([{ isIntersecting }])
  }
}

describe('DwellersList', () => {
  const roster = Array.from({ length: 45 }, (_, index) => dweller({ id: `dweller-${index}` }))

  const shallowList = (overrides: Partial<ListProps> = {}) =>
    shallowMount(DwellersList, {
      props: listProps(overrides),
      global: { stubs: { Button: false } },
    })

  const fullList = (overrides: Partial<ListProps> = {}, stubs: Record<string, unknown> = {}) =>
    mount(DwellersList, {
      props: listProps(overrides),
      global: { stubs: { Icon: true, ...stubs } },
    })

  const visibleIds = (wrapper: ReturnType<typeof shallowMount>, viewMode: string) =>
    viewMode === 'table'
      ? (
          wrapper.findComponent({ name: 'DwellersTable' }).props('dwellers') as { id: string }[]
        ).map((d) => d.id)
      : wrapper
          .findAllComponents({
            name: viewMode === 'list' ? 'DwellerListRow' : 'DwellerGridItem',
          })
          .map((row) => (row.props('dweller') as { id: string }).id)

  const loadMoreButton = (wrapper: ReturnType<typeof mount>, label = 'Show 20 more') =>
    wrapper.findAll('button').find((button) => button.text().includes(label))

  const intersectSentinel = async (isIntersecting = true) => {
    FakeIntersectionObserver.instances.at(-1)!.intersect(isIntersecting)
    await nextTick()
    await nextTick()
  }

  beforeEach(() => {
    FakeIntersectionObserver.instances = []
    vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('incremental rendering', () => {
    it.each(['list', 'grid', 'table'])(
      'caps the first render of the %s layout at 20 without changing roster order',
      async (viewMode) => {
        const wrapper = shallowList({ dwellers: roster, viewMode })
        await nextTick()

        expect(visibleIds(wrapper, viewMode)).toEqual(roster.slice(0, 20).map((d) => d.id))
        expect(wrapper.get('.dweller-progress').text()).toBe('Showing 20 of 45')
        expect(wrapper.find('[aria-label="Next dweller page"]').exists()).toBe(false)
        expect(wrapper.find('[aria-label="Previous dweller page"]').exists()).toBe(false)
      }
    )

    it.each(['list', 'grid', 'table'])(
      'appends the next 20 %s rows when the sentinel intersects',
      async (viewMode) => {
        const wrapper = shallowList({ dwellers: roster, viewMode })
        await nextTick()
        expect(FakeIntersectionObserver.instances).toHaveLength(1)

        await intersectSentinel()
        expect(visibleIds(wrapper, viewMode)).toEqual(roster.slice(0, 40).map((d) => d.id))
        expect(wrapper.get('.dweller-progress').text()).toBe('Showing 40 of 45')

        await intersectSentinel()
        expect(visibleIds(wrapper, viewMode)).toEqual(roster.map((d) => d.id))
        expect(wrapper.get('.dweller-progress').text()).toBe('Showing 45 of 45')
      }
    )

    it('ignores an observer entry that reports the sentinel leaving the viewport', async () => {
      const wrapper = shallowList({ dwellers: roster })
      await nextTick()

      await intersectSentinel(false)

      expect(visibleIds(wrapper, 'list')).toHaveLength(20)
    })

    it('observes the sentinel against the nearest scrolling ancestor, not the window', async () => {
      const scroller = document.createElement('div')
      scroller.style.overflowY = 'auto'
      document.body.appendChild(scroller)

      const wrapper = mount(DwellersList, {
        props: listProps({ dwellers: roster }),
        attachTo: scroller,
        global: { stubs: { Icon: true, Button: false } },
      })
      await nextTick()

      expect(FakeIntersectionObserver.instances.at(-1)!.options?.root).toBe(scroller)
      wrapper.unmount()
      scroller.remove()
    })

    it('resets to the first 20 when the roster is replaced by a filter or sort change', async () => {
      const wrapper = shallowList({ dwellers: roster })
      await nextTick()
      await intersectSentinel()
      expect(visibleIds(wrapper, 'list')).toHaveLength(40)

      const filtered = roster.filter((_, index) => index % 3 !== 2)
      await wrapper.setProps({ dwellers: filtered })

      expect(visibleIds(wrapper, 'list')).toEqual(filtered.slice(0, 20).map((d) => d.id))
      expect(wrapper.get('.dweller-progress').text()).toBe('Showing 20 of 30')
    })

    it('keeps the scroll depth when a single dweller is updated in place', async () => {
      const live = reactive(roster.map((d) => ({ ...d })))
      const wrapper = shallowList({ dwellers: live })
      await nextTick()
      await intersectSentinel()
      expect(visibleIds(wrapper, 'list')).toHaveLength(40)

      live[0]!.happiness = 12
      await nextTick()

      expect(visibleIds(wrapper, 'list')).toHaveLength(40)
    })

    it('keeps a load-more button so keyboard users can reach every dweller', async () => {
      const wrapper = fullList({ dwellers: roster })
      await nextTick()

      const button = loadMoreButton(wrapper)
      expect(button!.text()).toContain('Show 20 more')

      await button!.trigger('click')

      expect(visibleIds(wrapper, 'list')).toHaveLength(40)
      expect(loadMoreButton(wrapper, 'Show 5 more')).toBeDefined()
    })

    it('renders no sentinel and no load-more control when every dweller is shown', async () => {
      const wrapper = shallowList({ dwellers: roster.slice(0, 20) })
      await nextTick()

      expect(wrapper.find('.dweller-sentinel').exists()).toBe(false)
      expect(loadMoreButton(wrapper)).toBeUndefined()
      expect(wrapper.get('.dweller-progress').text()).toBe('Showing 20 of 20')
      expect(wrapper.get('.dweller-progress').attributes('aria-live')).toBeUndefined()
    })

    it('shows the progress line only once rows exist and loading has finished', async () => {
      const wrapper = shallowList({ dwellers: roster, isLoading: true })
      await nextTick()

      expect(wrapper.find('.dweller-progress').exists()).toBe(false)
      expect(wrapper.find('.dweller-sentinel').exists()).toBe(false)
    })

    it('disconnects the observer on unmount', async () => {
      const wrapper = shallowList({ dwellers: roster })
      await nextTick()
      const disconnect = vi.spyOn(FakeIntersectionObserver.instances.at(-1)!, 'disconnect')

      wrapper.unmount()

      expect(disconnect).toHaveBeenCalled()
    })

    it('keeps the scroll depth when changing layout and opens the dweller that was revealed', async () => {
      const wrapper = shallowList({ dwellers: roster })
      await nextTick()
      await intersectSentinel()

      await wrapper.setProps({ viewMode: 'grid' })
      wrapper.findComponent({ name: 'DwellerGridItem' }).vm.$emit('click')

      expect(wrapper.findAllComponents({ name: 'DwellerGridItem' })).toHaveLength(40)
      expect(wrapper.emitted('view-details')).toEqual([[roster[0]!.id]])
    })
  })

  it.each([
    ['list', 'ul', ['.dweller-grid', 'table']],
    ['grid', '.dweller-grid', ['ul', 'table']],
    ['table', 'table', ['ul', '.dweller-grid']],
  ])('renders only the %s layout for %s mode', async (viewMode, present, absent) => {
    const wrapper =
      viewMode === 'table'
        ? fullList({ dwellers: [dweller()], viewMode })
        : shallowList({ dwellers: [dweller()], viewMode })
    await nextTick()

    expect(wrapper.find(present).exists()).toBe(true)
    for (const selector of absent as string[]) {
      expect(wrapper.find(selector).exists()).toBe(false)
    }
  })

  describe('empty state', () => {
    it('offers a clear-filters action when no dweller matches the active filters', async () => {
      const wrapper = fullList({ hasActiveFilters: true })

      expect(wrapper.text()).toContain('No dwellers match these filters')

      const clearButton = wrapper.get('button')
      expect(clearButton.text()).toContain('Clear filters')

      await clearButton.trigger('click')

      expect(wrapper.emitted('clear-filters')).toHaveLength(1)
    })

    it('shows the empty-vault message without a clear action when no filters are active', () => {
      const wrapper = fullList()

      expect(wrapper.text()).toContain('No dwellers yet')
      expect(wrapper.text()).not.toContain('No dwellers match these filters')
      expect(wrapper.find('button').exists()).toBe(false)
    })

    it.each([
      ['while loading', { isLoading: true }],
      ['when the filtered list is not empty', { dwellers: [dweller()], hasActiveFilters: true }],
    ])('keeps rendering rows %s', async (_name, props) => {
      const wrapper = shallowList(props as Partial<ListProps>)

      expect(wrapper.text()).not.toContain('No dwellers yet')
      expect(wrapper.text()).not.toContain('No dwellers match these filters')
      expect(wrapper.find('ul').exists()).toBe(true)
    })
  })

  it('lays out a list row with combat power, identity and level under the name', () => {
    const wrapper = fullList(
      {
        dwellers: [dweller({ room_id: 'room-1' })],
        rooms: [{ id: 'room-1', name: 'Arena', category: 'arena', ability: 'strength' }] as never,
      },
      { DwellerListRow: false }
    )

    expect(wrapper.text()).toContain('Power:')
    expect(wrapper.text()).toContain('14')
    expect(wrapper.find('.dweller-identity').classes()).toContain('w-44')
    expect(wrapper.find('h3').classes()).toContain('truncate')
    expect(wrapper.find('li').classes()).toContain('bg-surface-canvas')
    expect(wrapper.find('li').classes()).toContain('border-theme-primary/20')

    const identity = wrapper.get('.dweller-identity')
    expect(identity.text()).toContain('Sarah Lyons')
    expect(identity.text()).toContain('Level 5')
    expect(identity.find('.dweller-meta-divider').exists()).toBe(false)
  })
})
