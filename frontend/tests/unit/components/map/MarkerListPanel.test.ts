import { describe, it, expect } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import MarkerListPanel from '@/modules/map/components/MarkerListPanel.vue'
import { createLocation, createSite, createVaultMarker } from '../../helpers/mapFixtures'
import type { WastelandLocationWithDwellers } from '@/modules/map/models/map'

const IconStub = { name: 'Icon', props: ['icon'], template: '<span />' }

/** Positional adapter around the shared location fixture. */
function location(
  type: string,
  name: string,
  id = name.toLowerCase().replace(/\s+/g, '-')
): WastelandLocationWithDwellers {
  return createLocation({
    id,
    name,
    normalized_name: name.toLowerCase(),
    type: type as WastelandLocationWithDwellers['type'],
  })
}

function mountPanel(
  props: Record<string, unknown> = {},
  options: {
    stubs?: Record<string, unknown>
    slots?: Record<string, string>
    attachTo?: boolean
  } = {}
) {
  return mount(MarkerListPanel, {
    props: { locations: [], vaultMarkers: [], ...props },
    global: { stubs: { Icon: IconStub, ...options.stubs } },
    ...(options.slots ? { slots: options.slots } : {}),
    ...(options.attachTo ? { attachTo: document.body } : {}),
  })
}

describe('MarkerListPanel', () => {
  it('preserves place selection, filters, and list scroll when switching to the legend', async () => {
    const wrapper = mountPanel(
      {
        locations: [{ ...location('discovery', 'Depot', 'depot'), group_key: 'gas_station' }],
        docked: true,
        siteTypeFilter: 'gas_station',
        selectedMarkerId: 'loc-depot',
        activeFilterCount: 1,
      },
      {
        attachTo: true,
        slots: {
          filters: '<p>Gas station filter</p>',
          legend: '<p>Full map legend</p>',
        },
      }
    )
    const list = wrapper.find('.panel-body').element
    list.scrollTop = 120
    await wrapper.findAll('[role="tab"]')[1].trigger('mousedown')
    await flushPromises()
    expect(wrapper.find('.panel-body').exists()).toBe(true)
    expect(wrapper.find('.panel-body').isVisible()).toBe(false)
    expect(wrapper.text()).toContain('Full map legend')
    await wrapper.findAll('[role="tab"]')[0].trigger('mousedown')
    await flushPromises()
    expect(wrapper.find('.panel-body').element).toBe(list)
    expect(list.scrollTop).toBe(120)
    expect(wrapper.find('.marker-row.selected').text()).toContain('Depot')
    expect(wrapper.text()).toContain('Gas station filter')
    wrapper.unmount()
  })

  describe('Rendering', () => {
    it('renders a toggle and keeps the panel closed by default', () => {
      // jsdom 31 needs the node in the document to resolve the v-show display.
      const wrapper = mountPanel({ locations: [location('origin', 'Megaton')] }, { attachTo: true })
      expect(wrapper.find('.marker-list-toggle').exists()).toBe(true)
      expect(wrapper.find('.marker-list-panel').isVisible()).toBe(false)
      wrapper.unmount()
    })

    it.each([
      ['open=true', { open: true }],
      ['docked', { docked: true }],
    ])('keeps the index visible with %s', (_, props) => {
      const wrapper = mountPanel({ locations: [location('origin', 'Megaton')], ...props })
      expect(wrapper.find('.marker-list-panel').isVisible()).toBe(true)
      if ('docked' in props) expect(wrapper.find('.marker-list-toggle').exists()).toBe(false)
    })

    it('shows the site-type group for a location', () => {
      const wrapper = mountPanel({
        locations: [{ ...location('visited', 'Red Rocket'), group_key: 'gas_station' }],
        placeGroups: [
          {
            key: 'gas_station',
            label: 'Gas Station',
            icon: 'mdi:gas-station',
            risk: 'low',
            description: 'A roadside fuel stop.',
          },
        ],
        open: true,
      })
      expect(wrapper.text()).toContain('Gas Station')
      expect(wrapper.text()).toContain('Low risk')
    })
  })

  describe('Grouping', () => {
    it('groups markers by type in the correct order', () => {
      const wrapper = mountPanel({
        locations: [
          location('visited', 'Rivet City'),
          location('origin', 'Megaton'),
          location('home_vault', 'Vault 101'),
          location('discovery', 'Unknown Ruins'),
        ],
        vaultMarkers: [createVaultMarker({ name: 'Vault 88' })],
        open: true,
      })

      // All 5 types have markers, so 5 groups, labelled in display order.
      expect(wrapper.findAll('.group-header')).toHaveLength(5)
      const text = wrapper.text()
      const order = ['Home Vault', 'Origin', 'Visited', 'Discovery', 'Vault Signal'].map((label) =>
        text.indexOf(label)
      )
      for (let i = 1; i < order.length; i++) expect(order[i - 1]).toBeLessThan(order[i])
    })

    it('counts the markers and renders one clickable row each', () => {
      const wrapper = mountPanel({
        locations: [location('origin', 'Megaton'), location('visited', 'Rivet City')],
        vaultMarkers: [createVaultMarker({ name: 'Vault 88' })],
        open: true,
      })
      expect(wrapper.find('.panel-count').text()).toBe('3')
      const rows = wrapper.findAll('.marker-row')
      expect(rows).toHaveLength(3)
      expect(rows[0].text()).toContain('Megaton')
      expect(rows[2].text()).toContain('Vault 88')
    })
  })

  describe('Click interaction', () => {
    const megaton = location('origin', 'Megaton')
    const vault = createVaultMarker({ name: 'Vault 88' })
    const site = createSite()

    it.each([
      ['location', { locations: [megaton] }, { kind: 'location', data: megaton }],
      ['vault', { vaultMarkers: [vault] }, { kind: 'vault', data: vault }],
      ['site', { expeditionSites: [site] }, { kind: 'site', data: site }],
    ])('emits marker-select with kind=%s for a clicked row', async (_, props, expected) => {
      const wrapper = mountPanel({ ...props, open: true })
      await wrapper.findAll('.marker-row')[0].trigger('click')
      expect(wrapper.emitted('marker-select')![0][0]).toEqual(expected)
    })

    it('highlights the selected marker row', () => {
      const row = mountPanel({
        locations: [location('origin', 'Megaton')],
        selectedMarkerId: 'loc-megaton',
        open: true,
      }).find('.marker-row.selected')
      expect(row.exists()).toBe(true)
      expect(row.text()).toContain('Megaton')
    })
  })

  describe('Toggle', () => {
    it('should toggle panel open state on button click', async () => {
      const wrapper = mountPanel()

      await wrapper.find('.marker-list-toggle').trigger('click')
      // defineModel emits update:open when toggled
      expect(wrapper.emitted('update:open')![0][0]).toBe(true)

      await wrapper.find('.marker-list-toggle').trigger('click')
      expect(wrapper.emitted('update:open')![1][0]).toBe(false)
    })
  })

  describe('Empty state', () => {
    it('should show empty message when no markers', () => {
      expect(mountPanel({ open: true }).text()).toContain('No markers yet')
    })

    it('explains that an empty result is caused by the active filters', () => {
      const text = mountPanel({ activeFilterCount: 1, open: true }).text()
      expect(text).toContain('No markers match these filters')
      expect(text).not.toContain('No markers yet')
    })
  })

  describe('Vault group styling', () => {
    it('should vault-style only the vault group', () => {
      const groups = mountPanel({
        locations: [location('origin', 'Megaton')],
        vaultMarkers: [createVaultMarker({ name: 'Vault 88' })],
        open: true,
      }).findAll('.marker-group-vault')
      expect(groups).toHaveLength(1)
      expect(groups[0].text()).toContain('Vault Signal')
    })

    it('should NOT vault-style the last location group when no vault markers exist', () => {
      const wrapper = mountPanel({
        locations: [location('origin', 'Megaton'), location('discovery', 'Unknown Ruins')],
        open: true,
      })
      expect(wrapper.find('.marker-group-vault').exists()).toBe(false)
      const groups = wrapper.findAll('.marker-group')
      expect(groups[groups.length - 1].classes()).not.toContain('marker-group-vault')
    })
  })

  describe('Expedition sites group', () => {
    it('groups expedition sites under their own group and counts them', () => {
      const wrapper = mountPanel({
        locations: [location('origin', 'Megaton')],
        vaultMarkers: [createVaultMarker({ name: 'Vault 88' })],
        expeditionSites: [createSite()],
        open: true,
      })
      expect(wrapper.text()).toContain('Expedition Sites')
      expect(wrapper.text()).toContain('Red Rocket Gas Station')
      expect(wrapper.find('.panel-count').text()).toBe('3')
    })

    it('renders no expedition group when no sites exist', () => {
      expect(
        mountPanel({ locations: [location('origin', 'Megaton')], open: true }).text()
      ).not.toContain('Expedition Sites')
    })
  })

  describe('Keyboard navigation', () => {
    function mountAttached(locations: WastelandLocationWithDwellers[]) {
      return mountPanel({ locations, open: true }, { attachTo: true })
    }

    function keydown(el: Element, key: string) {
      el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
    }

    it('moves focus with ArrowDown and ArrowUp across rows', async () => {
      const wrapper = mountAttached([location('discovery', 'Alpha'), location('discovery', 'Beta')])

      const rows = wrapper.findAll('button.marker-row')
      expect(rows).toHaveLength(2)
      ;(rows[0].element as HTMLElement).focus()
      expect(document.activeElement).toBe(rows[0].element)

      keydown(wrapper.find('.panel-body').element, 'ArrowDown')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[1].element)

      keydown(wrapper.find('.panel-body').element, 'ArrowUp')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[0].element)
      wrapper.unmount()
    })

    it('wraps focus at the ends and jumps with Home and End', async () => {
      const wrapper = mountAttached([location('discovery', 'Alpha'), location('discovery', 'Beta')])

      const body = wrapper.find('.panel-body').element
      const rows = wrapper.findAll('button.marker-row')
      ;(rows[1].element as HTMLElement).focus()

      keydown(body, 'ArrowDown')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[0].element)

      keydown(body, 'End')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[1].element)

      keydown(body, 'Home')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[0].element)
      wrapper.unmount()
    })

    it('skips rows in collapsed groups', async () => {
      const wrapper = mountAttached([location('discovery', 'Alpha'), location('visited', 'Beta')])

      const headers = wrapper.findAll('button.group-header')
      expect(headers.length).toBeGreaterThanOrEqual(2)
      await headers[0].trigger('click')

      const rows = wrapper.findAll('button.marker-row')
      ;(rows[1].element as HTMLElement).focus()
      keydown(wrapper.find('.panel-body').element, 'ArrowDown')
      await wrapper.vm.$nextTick()
      expect(document.activeElement).toBe(rows[1].element)
      wrapper.unmount()
    })

    it('activates the focused row with Enter', async () => {
      const megaton = location('origin', 'Megaton')
      const wrapper = mountAttached([megaton])

      const row = wrapper.findAll('button.marker-row')[0]
      ;(row.element as HTMLElement).focus()
      keydown(row.element, 'Enter')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-select')![0][0]).toEqual({ kind: 'location', data: megaton })
      wrapper.unmount()
    })
  })

  describe('Site-type filter', () => {
    const PLACE_GROUPS = [
      {
        key: 'gas_station',
        label: 'Gas Station',
        icon: 'mdi:gas-station',
        risk: 'low',
        description: 'A roadside fuel stop.',
        clearable: false,
      },
      {
        key: 'military',
        label: 'Military',
        icon: 'mdi:shield-cross',
        risk: 'high',
        description: 'A fortified base.',
        clearable: false,
      },
    ]

    const grouped = (type: string, name: string, groupKey: string) => ({
      ...location(type, name),
      group_key: groupKey,
    })

    const mountFiltered = (locations: WastelandLocationWithDwellers[], filter: string | null) =>
      mountPanel({ locations, placeGroups: PLACE_GROUPS, siteTypeFilter: filter, open: true })

    const bothSites = () => [
      grouped('visited', 'Gas Stop', 'gas_station'),
      grouped('visited', 'Army Base', 'military'),
    ]

    it('lists and counts only locations of the selected site type', () => {
      const wrapper = mountFiltered(bothSites(), 'gas_station')
      const rows = wrapper.findAll('.marker-row')
      expect(rows).toHaveLength(1)
      expect(rows[0].text()).toContain('Gas Stop')
      expect(wrapper.text()).not.toContain('Army Base')
      expect(wrapper.find('.panel-count').text()).toBe('1')
    })

    it('drops groups left without items under the filter', () => {
      const wrapper = mountFiltered(
        [
          grouped('discovery', 'Unknown Ruins', 'gas_station'),
          grouped('visited', 'Gas Stop', 'gas_station'),
          grouped('visited', 'Army Base', 'military'),
        ],
        'military'
      )
      const headers = wrapper.findAll('.group-header')
      expect(headers).toHaveLength(1)
      expect(headers[0].text()).toContain('Visited')
      expect(wrapper.text()).not.toContain('Unknown Ruins')
      expect(wrapper.text()).not.toContain('Gas Stop')
    })

    it('shows every location when the filter is null', () => {
      const wrapper = mountFiltered(bothSites(), null)
      expect(wrapper.findAll('.marker-row')).toHaveLength(2)
      expect(wrapper.find('.panel-count').text()).toBe('2')
    })

    it('keeps the home vault, which is not a site type', () => {
      const text = mountFiltered(
        [grouped('visited', 'Gas Stop', 'gas_station'), location('home_vault', 'Vault 42')],
        'gas_station'
      ).text()
      expect(text).toContain('Gas Stop')
      expect(text).toContain('Vault 42')
    })

    it('still counts vaults and expedition sites under a filter', () => {
      const wrapper = mountPanel({
        locations: bothSites(),
        vaultMarkers: [createVaultMarker({ name: 'Vault 88' })],
        expeditionSites: [createSite()],
        placeGroups: PLACE_GROUPS,
        siteTypeFilter: 'gas_station',
        open: true,
      })
      expect(wrapper.find('.panel-count').text()).toBe('3')
      expect(wrapper.text()).toContain('Vault 88')
      expect(wrapper.text()).toContain('Red Rocket Gas Station')
    })
  })
})

describe('MarkerListPanel — sets tab', () => {
  it('shows the sets tab only while sets exist and falls back to places when they vanish', async () => {
    const wrapper = mountPanel(
      { hasSets: true },
      { slots: { legend: '<p>Full map legend</p>', sets: '<p>Set progress body</p>' } }
    )
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual([
      'Places',
      'Legend',
      'Sets',
    ])

    await wrapper.findAll('[role="tab"]')[2].trigger('mousedown')
    await flushPromises()
    expect(wrapper.text()).toContain('Set progress body')
    expect(wrapper.find('.panel-title').text()).toBe('SETS')

    await wrapper.setProps({ hasSets: false })
    await flushPromises()
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual(['Places', 'Legend'])
    expect(wrapper.find('.panel-title').text()).toBe('PLACES AND SITES')
    expect(wrapper.text()).not.toContain('Set progress body')
    expect(wrapper.find('.panel-body').isVisible()).toBe(true)
  })
})
