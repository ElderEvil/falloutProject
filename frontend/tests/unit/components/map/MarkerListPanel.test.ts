import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkerListPanel from '@/modules/map/components/MarkerListPanel.vue'
import type {
  ExpeditionSiteMarkerRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '@/modules/map/models/map'

function createLocation(
  type: string,
  name: string,
  id = name.toLowerCase().replace(/\s+/g, '-')
): WastelandLocationWithDwellers {
  return {
    id,
    name,
    normalized_name: name.toLowerCase(),
    type: type as WastelandLocationWithDwellers['type'],
    coord_x: 50,
    coord_y: 50,
    description: null,
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: null,
    dwellers: [],
  }
}

function createVault(name: string): VaultMarkerRead {
  return {
    name,
    coord_x: 30,
    coord_y: 40,
    type: 'vault',
    description: 'Unexplored vault signal',
  }
}

function createSite(overrides: Partial<ExpeditionSiteMarkerRead> = {}): ExpeditionSiteMarkerRead {
  return {
    id: 'site-1',
    name: 'Red Rocket Gas Station',
    flavor: 'A roadside fuel stop.',
    coord_x: 60,
    coord_y: 70,
    min_dweller_level: 5,
    room_total: 3,
    cleared: false,
    cooldown_remaining_seconds: 0,
    block_reason: null,
    ...overrides,
  }
}

const IconStub = { name: 'Icon', props: ['icon'], template: '<span />' }

describe('MarkerListPanel', () => {
  describe('Rendering', () => {
    it('should render the toggle button', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [],
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.marker-list-toggle').exists()).toBe(true)
    })

    it('should NOT show the panel by default (closed)', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [],
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.marker-list-panel').isVisible()).toBe(false)
    })

    it('should show panel when open=true', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.marker-list-panel').isVisible()).toBe(true)
    })

    it('shows the site-type group for a location', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [{ ...createLocation('visited', 'Red Rocket'), group_key: 'gas_station' }],
          vaultMarkers: [],
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
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.text()).toContain('Gas Station')
    })

    it('should keep the index visible without a toggle when docked', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [],
          docked: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.marker-list-toggle').exists()).toBe(false)
      expect(wrapper.find('.marker-list-panel').isVisible()).toBe(true)
    })
  })

  describe('Grouping', () => {
    it('should group markers by type in the correct order', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [
            createLocation('visited', 'Rivet City'),
            createLocation('origin', 'Megaton'),
            createLocation('home_vault', 'Vault 101'),
            createLocation('discovery', 'Unknown Ruins'),
          ],
          vaultMarkers: [createVault('Vault 88')],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      const groups = wrapper.findAll('.group-header')
      // All 5 types have markers, so 5 groups
      expect(groups.length).toBe(5)

      // Check group labels appear in order
      const text = wrapper.text()
      const homeIdx = text.indexOf('Home Vault')
      const originIdx = text.indexOf('Origin')
      const visitedIdx = text.indexOf('Visited')
      const discoveryIdx = text.indexOf('Discovery')
      const vaultIdx = text.indexOf('Vault Signal')

      expect(homeIdx).toBeLessThan(originIdx)
      expect(originIdx).toBeLessThan(visitedIdx)
      expect(visitedIdx).toBeLessThan(discoveryIdx)
      expect(discoveryIdx).toBeLessThan(vaultIdx)
    })

    it('should show total marker count in header', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'A'), createLocation('visited', 'B')],
          vaultMarkers: [createVault('C')],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.panel-count').text()).toBe('3')
    })

    it('should render each marker as a clickable row', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [createVault('Vault 88')],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      const rows = wrapper.findAll('.marker-row')
      expect(rows).toHaveLength(2)
      expect(rows[0].text()).toContain('Megaton')
      expect(rows[1].text()).toContain('Vault 88')
    })
  })

  describe('Click interaction', () => {
    it('should emit marker-select when a row is clicked', async () => {
      const loc = createLocation('origin', 'Megaton')
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [loc],
          vaultMarkers: [],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      await wrapper.findAll('.marker-row')[0].trigger('click')

      expect(wrapper.emitted('marker-select')).toBeTruthy()
      expect(wrapper.emitted('marker-select')![0][0]).toEqual({
        kind: 'location',
        data: loc,
      })
    })

    it('should emit marker-select for vault markers', async () => {
      const vm = createVault('Vault 88')
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [vm],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      await wrapper.findAll('.marker-row')[0].trigger('click')

      expect(wrapper.emitted('marker-select')![0][0]).toEqual({
        kind: 'vault',
        data: vm,
      })
    })

    it('should highlight the selected marker row', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [],
          open: true,
          selectedMarkerId: 'loc-megaton',
        },
        global: { stubs: { Icon: IconStub } },
      })

      const row = wrapper.find('.marker-row.selected')
      expect(row.exists()).toBe(true)
      expect(row.text()).toContain('Megaton')
    })
  })

  describe('Toggle', () => {
    it('should toggle panel open state on button click', async () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [],
        },
        global: { stubs: { Icon: IconStub } },
      })

      await wrapper.find('.marker-list-toggle').trigger('click')
      // defineModel emits update:open when toggled
      const emitted = wrapper.emitted('update:open')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toBe(true)

      // Second click should toggle back to false
      await wrapper.find('.marker-list-toggle').trigger('click')
      expect(wrapper.emitted('update:open')![1][0]).toBe(false)
    })
  })

  describe('Empty state', () => {
    it('should show empty message when no markers', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.text()).toContain('No markers yet')
    })
  })

  describe('Vault group styling', () => {
    it('should vault-style only the vault group', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [createVault('Vault 88')],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      const vaultGroups = wrapper.findAll('.marker-group-vault')
      expect(vaultGroups).toHaveLength(1)
      expect(vaultGroups[0].text()).toContain('Vault Signal')
    })

    it('should NOT vault-style the last location group when no vault markers exist', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [
            createLocation('origin', 'Megaton'),
            createLocation('discovery', 'Unknown Ruins'),
          ],
          vaultMarkers: [],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.marker-group-vault').exists()).toBe(false)

      const groups = wrapper.findAll('.marker-group')
      const lastGroup = groups[groups.length - 1]
      expect(lastGroup.classes()).not.toContain('marker-group-vault')
    })
  })

  describe('Expedition sites group', () => {
    it('groups expedition sites under their own group', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [],
          expeditionSites: [createSite()],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.text()).toContain('Expedition Sites')
      expect(wrapper.text()).toContain('Red Rocket Gas Station')
    })

    it('counts expedition sites in the panel total', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [createVault('Vault 88')],
          expeditionSites: [createSite()],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.panel-count').text()).toBe('3')
    })

    it('emits marker-select with kind=site when a site row is clicked', async () => {
      const site = createSite()
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [],
          vaultMarkers: [],
          expeditionSites: [site],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      await wrapper.findAll('.marker-row')[0].trigger('click')

      expect(wrapper.emitted('marker-select')![0][0]).toEqual({
        kind: 'site',
        data: site,
      })
    })

    it('renders no expedition group when no sites exist', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [createLocation('origin', 'Megaton')],
          vaultMarkers: [],
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.text()).not.toContain('Expedition Sites')
    })
  })

  describe('Keyboard navigation', () => {
    function mountAttached(locations: WastelandLocationWithDwellers[]) {
      return mount(MarkerListPanel, {
        props: { locations, vaultMarkers: [], open: true },
        global: { stubs: { Icon: IconStub } },
        attachTo: document.body,
      })
    }

    function keydown(el: Element, key: string) {
      el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
    }

    it('moves focus with ArrowDown and ArrowUp across rows', async () => {
      const wrapper = mountAttached([
        createLocation('discovery', 'Alpha'),
        createLocation('discovery', 'Beta'),
      ])

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
      const wrapper = mountAttached([
        createLocation('discovery', 'Alpha'),
        createLocation('discovery', 'Beta'),
      ])

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
      const wrapper = mountAttached([
        createLocation('discovery', 'Alpha'),
        createLocation('visited', 'Beta'),
      ])

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
      const loc = createLocation('origin', 'Megaton')
      const wrapper = mountAttached([loc])

      const row = wrapper.findAll('button.marker-row')[0]
      ;(row.element as HTMLElement).focus()
      keydown(row.element, 'Enter')
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('marker-select')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toEqual({ kind: 'location', data: loc })
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

    function groupedLocation(type: string, name: string, groupKey: string) {
      return { ...createLocation(type, name), group_key: groupKey }
    }

    function mountFiltered(locations: WastelandLocationWithDwellers[], filter: string | null) {
      return mount(MarkerListPanel, {
        props: {
          locations,
          vaultMarkers: [],
          placeGroups: PLACE_GROUPS,
          siteTypeFilter: filter,
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })
    }

    it('lists only locations of the selected site type', () => {
      const wrapper = mountFiltered(
        [
          groupedLocation('visited', 'Gas Stop', 'gas_station'),
          groupedLocation('visited', 'Army Base', 'military'),
        ],
        'gas_station'
      )

      const rows = wrapper.findAll('.marker-row')
      expect(rows).toHaveLength(1)
      expect(rows[0].text()).toContain('Gas Stop')
      expect(wrapper.text()).not.toContain('Army Base')
    })

    it('recomputes the total count from the filtered set', () => {
      const wrapper = mountFiltered(
        [
          groupedLocation('visited', 'Gas Stop', 'gas_station'),
          groupedLocation('visited', 'Army Base', 'military'),
        ],
        'gas_station'
      )

      expect(wrapper.find('.panel-count').text()).toBe('1')
    })

    it('drops groups left without items under the filter', () => {
      const wrapper = mountFiltered(
        [
          groupedLocation('discovery', 'Unknown Ruins', 'gas_station'),
          groupedLocation('visited', 'Gas Stop', 'gas_station'),
          groupedLocation('visited', 'Army Base', 'military'),
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
      const wrapper = mountFiltered(
        [
          groupedLocation('visited', 'Gas Stop', 'gas_station'),
          groupedLocation('visited', 'Army Base', 'military'),
        ],
        null
      )

      expect(wrapper.findAll('.marker-row')).toHaveLength(2)
      expect(wrapper.find('.panel-count').text()).toBe('2')
    })

    it('keeps the home vault, which is not a site type', () => {
      const wrapper = mountFiltered(
        [
          groupedLocation('visited', 'Gas Stop', 'gas_station'),
          createLocation('home_vault', 'Vault 42'),
        ],
        'gas_station'
      )

      expect(wrapper.text()).toContain('Gas Stop')
      expect(wrapper.text()).toContain('Vault 42')
    })

    it('still counts vaults and expedition sites under a filter', () => {
      const wrapper = mount(MarkerListPanel, {
        props: {
          locations: [
            groupedLocation('visited', 'Gas Stop', 'gas_station'),
            groupedLocation('visited', 'Army Base', 'military'),
          ],
          vaultMarkers: [createVault('Vault 88')],
          expeditionSites: [createSite()],
          placeGroups: PLACE_GROUPS,
          siteTypeFilter: 'gas_station',
          open: true,
        },
        global: { stubs: { Icon: IconStub } },
      })

      expect(wrapper.find('.panel-count').text()).toBe('3')
      expect(wrapper.text()).toContain('Vault 88')
      expect(wrapper.text()).toContain('Red Rocket Gas Station')
    })
  })
})
