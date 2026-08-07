import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkerListPanel from '@/modules/map/components/MarkerListPanel.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '@/modules/map/models/map'

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
})
