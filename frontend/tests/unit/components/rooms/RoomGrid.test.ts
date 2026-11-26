import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createRouterMock } from '../../helpers/mocks'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { useRoute } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import RoomGrid from '@/modules/rooms/components/RoomGrid.vue'
import RoomGridCell from '@/modules/rooms/components/RoomGridCell.vue'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

// TooltipLabel is a thin presentational wrapper; stubbing it lets isolated cell
// mounts skip the TooltipProvider ancestor and exposes each label as text.
const tooltipLabelStub = {
  name: 'TooltipLabel',
  props: ['label'],
  template: '<div><slot /><span class="tooltip-label">{{ label }}</span></div>',
}

const roomDetailModalStub = {
  name: 'RoomDetailModal',
  template: '<div data-testid="room-detail-modal" />',
}

const mockRoom = {
  id: 'room-123',
  name: 'Power Generator',
  category: 'power',
  ability: 'strength',
  coordinate_x: 0,
  coordinate_y: 0,
  size: 3,
  size_min: 3,
  tier: 1,
  capacity: 6,
}

const dinerTemplate = {
  name: 'Diner',
  category: 'production',
  ability: 'agility',
  base_cost: 100,
  t2_upgrade_cost: 200,
  t3_upgrade_cost: 400,
  size_min: 3,
  size_max: 9,
  tier: 1,
}

const elevatorTemplate = {
  name: 'Elevator',
  category: 'misc',
  ability: null,
  base_cost: 100,
  t2_upgrade_cost: null,
  t3_upgrade_cost: null,
  size_min: 1,
  size_max: 1,
  tier: 1,
}

const elevatorRoom = {
  ...mockRoom,
  id: 'elev-1',
  name: 'Elevator',
  category: 'misc',
  ability: null,
  coordinate_x: 0,
  coordinate_y: 1,
  size: 1,
  size_min: 1,
}

const trainingRoom = {
  ...mockRoom,
  id: 'training-room-123',
  name: 'Weight Room',
  category: 'training',
}

const productionRoom = {
  ...mockRoom,
  id: 'production-room-123',
  name: 'Power Generator',
  category: 'production',
}

const incident = { id: 'incident-1', room_id: 'room-123', type: 'FIRE', severity: 'medium' }

const render = (props: Record<string, unknown> = {}): VueWrapper =>
  mount(RoomGrid, {
    props: { incidents: [], ...props },
    global: { stubs: { RoomDetailModal: roomDetailModalStub } },
  })

const renderCell = (room: Record<string, unknown>, props: Record<string, unknown> = {}) =>
  mount(RoomGridCell, {
    props: {
      room,
      showRoomImages: false,
      isPowerOutage: false,
      selected: false,
      isDraggingOver: false,
      highlighted: false,
      ...props,
    },
    global: { stubs: { TooltipLabel: tooltipLabelStub } },
  })

const placing = (
  template: Record<string, unknown>,
  rooms: Record<string, unknown>[] = [mockRoom]
) => {
  const store = useRoomStore()
  store.rooms = rooms as never
  store.selectedRoom = template as never
  store.isPlacingRoom = true
  return store
}

const dropEventFor = (dwellerId: string) => ({
  preventDefault: vi.fn(),
  dataTransfer: {
    getData: vi.fn(() =>
      JSON.stringify({ dwellerId, firstName: 'X', lastName: 'Y', currentRoomId: null })
    ),
  },
})

const dropOn = async (wrapper: VueWrapper, dwellerId: string) => {
  await wrapper.find('.built-room').trigger('drop', dropEventFor(dwellerId) as any)
  await wrapper.vm.$nextTick()
}

/** The grid cell at a 1-based row/column pair. */
const cellAt = (wrapper: VueWrapper, row: number, column: number) =>
  wrapper
    .findAll('.empty')
    .find(
      (cell) =>
        (cell.element as HTMLElement).style.gridRow === String(row) &&
        parseInt((cell.element as HTMLElement).style.gridColumn, 10) === column
    )!

describe('RoomGrid', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    delete useRoute().query.dweller
    const { toasts } = useToast()
    toasts.value = []
  })

  it('keeps the assignment hint active while dragging between room children', async () => {
    useRoomStore().rooms = [mockRoom]
    const wrapper = render()
    const room = wrapper.get('.built-room')
    await room.trigger('dragover', { dataTransfer: { dropEffect: '' } })
    expect(room.text()).toContain('Drop to assign')

    await room.trigger('dragleave', { relatedTarget: room.get('.room-name').element })
    expect(room.text()).toContain('Drop to assign')

    await room.trigger('dragleave', { relatedTarget: document.body })
    expect(room.text()).not.toContain('Drop to assign')
  })

  it('highlights the room main stat while a dweller is dragged over it', async () => {
    useRoomStore().rooms = [mockRoom]
    const wrapper = render()
    const room = wrapper.get('.built-room')

    expect(room.find('.ability-icon--drag-over').exists()).toBe(false)

    await room.trigger('dragover', { dataTransfer: { dropEffect: '' } })
    expect(room.find('.ability-icon--drag-over').exists()).toBe(true)
    expect(room.text()).toContain('S · Strength')

    await room.trigger('dragleave', { relatedTarget: document.body })
    expect(room.find('.ability-icon--drag-over').exists()).toBe(false)
  })

  it('names empty room cells for screen-reader users', () => {
    const wrapper = render()

    expect(wrapper.find('.room.empty').attributes('aria-label')).toBe(
      'Empty room cell at row 1, column 1'
    )
    expect(wrapper.find('.room.empty').attributes('role')).toBe('img')
  })

  it('defers the room detail modal until a room is opened', async () => {
    useRoomStore().rooms = [mockRoom]
    const wrapper = render()
    expect(wrapper.find('[data-testid="room-detail-modal"]').exists()).toBe(false)
    await wrapper.get('.built-room').trigger('click')
    expect(wrapper.find('[data-testid="room-detail-modal"]').exists()).toBe(true)
  })

  it('uses the visible room text as its accessible name', () => {
    useRoomStore().rooms = [mockRoom]
    const wrapper = render()
    expect(wrapper.get('.built-room').attributes('aria-label')).toBeUndefined()
    expect(wrapper.get('.built-room').text()).toContain('T1')
  })

  describe('Room Highlighting', () => {
    it('shows an attention count only on the Overseer’s Office', () => {
      useRoomStore().rooms = [
        { ...mockRoom, id: 'office-123', name: "Overseer's Office" },
        mockRoom,
      ]

      const wrapper = render({ overseerAttentionCount: 3 })

      expect(wrapper.findAll('.overseer-alert-badge')).toHaveLength(1)
      expect(wrapper.find('.overseer-alert-badge').text()).toBe('3 items need attention')

      useRoomStore().rooms = [mockRoom]
      expect(render({ overseerAttentionCount: 3 }).find('.overseer-alert-badge').exists()).toBe(
        false
      )
    })

    it.each([
      ['room-123', null, true],
      ['different-room-id', null, false],
      [null, null, false],
      ['room-123', 'FIRE', true],
    ])(
      'marks room %s (incident %s) as highlighted=%s',
      (highlightedRoomId, incidentType, highlighted) => {
        useRoomStore().rooms = [mockRoom]

        const wrapper = render({
          highlightedRoomId,
          incidents: incidentType ? [{ ...incident, type: incidentType }] : [],
        })
        const builtRoom = wrapper.find('.built-room')

        expect(builtRoom.classes().includes('highlighted')).toBe(highlighted)
      }
    )

    it('only highlights the matching room when several exist', () => {
      useRoomStore().rooms = [mockRoom, { ...mockRoom, id: 'room-456', name: 'Diner' }]

      const builtRooms = render({ highlightedRoomId: 'room-123' }).findAll('.built-room')

      expect(builtRooms).toHaveLength(2)
      expect(builtRooms[0].classes()).toContain('highlighted')
      expect(builtRooms[1].classes()).not.toContain('highlighted')
    })

    it('marks a highlighted room that also has a live incident', () => {
      useRoomStore().rooms = [mockRoom]

      const wrapper = render({ highlightedRoomId: 'room-123', incidents: [incident] })

      expect(wrapper.find('.built-room').classes()).toEqual(
        expect.arrayContaining(['highlighted', 'has-incident'])
      )
    })

    it.each(['enter', 'space'] as const)(
      'does not emit the room click when %s activates the incident badge',
      async (key) => {
        const wrapper = renderCell(mockRoom, { showRoomImages: true, incident })

        const badge = wrapper.find('.incident-badge')
        expect(badge.exists()).toBe(true)
        await badge.trigger(`keydown.${key}`)

        expect(wrapper.emitted('incident-click')).toBeTruthy()
        expect(wrapper.emitted('click')).toBeFalsy()
      }
    )
  })

  describe('Elevator Gating', () => {
    it('renders empty cells on all levels but locks levels without an elevator', () => {
      useRoomStore().rooms = [mockRoom]

      const wrapper = render()

      // Cells render on every level …
      expect(wrapper.findAll('.empty').length).toBeGreaterThan(8)
      // … but only row 0 is unlocked.
      const unlockedRows = wrapper
        .findAll('.empty:not(.level-locked)')
        .map((cell) => (cell.element as HTMLElement).style.gridRow)
      expect(unlockedRows.every((row) => row === '1')).toBe(true)
    })

    it('unlocks a level when an elevator is built on it', () => {
      useRoomStore().rooms = [
        mockRoom,
        { ...mockRoom, id: 'elev-1', name: 'Elevator', coordinate_x: 0, coordinate_y: 3 },
      ]

      const unlockedRows = render()
        .findAll('.empty:not(.level-locked)')
        .map((cell) => (cell.element as HTMLElement).style.gridRow)

      expect(unlockedRows).toContain('4')
    })

    it('allows a standard room beside a one-unit elevator on the same level', async () => {
      placing(dinerTemplate, [
        mockRoom,
        {
          ...mockRoom,
          id: 'elev-1',
          name: 'Elevator',
          coordinate_x: 6,
          coordinate_y: 1,
          size: 1,
          size_min: 1,
        },
      ])

      const cell = cellAt(render(), 2, 8)
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('valid-placement')
    })

    it('marks an elevator preview as invalid when there is no elevator above', async () => {
      placing(elevatorTemplate)

      const cell = render().findAll('.empty:not(.level-locked)')[1]
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('invalid-placement')
    })

    it('allows an elevator preview on a locked level when stacked under one', async () => {
      placing(elevatorTemplate, [
        mockRoom,
        { ...mockRoom, id: 'elev-1', name: 'Elevator', coordinate_x: 6, coordinate_y: 3 },
      ])

      // Level 4 has no elevator (locked) but is directly below the level-3
      // elevator, so an elevator preview there must be valid. While placing
      // an elevator the locked styling is lifted so the cell is interactive.
      const cell = cellAt(render(), 5, 7)
      expect(cell.classes()).not.toContain('level-locked')
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('valid-placement')
    })

    it('marks a non-elevator preview as invalid on a level without an elevator', async () => {
      placing(dinerTemplate)

      // Hover the first cell on a locked level (row 1+, no elevator)
      const cell = render().findAll('.empty.level-locked')[0]!
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('level-locked')
      expect(cell.classes()).not.toContain('hover-preview')
    })
  })

  describe('Room placement', () => {
    it('rejects a gap in both the preview and click handler', async () => {
      const roomStore = placing(dinerTemplate, [
        { ...mockRoom, id: 'shaft', name: 'Elevator', coordinate_x: 6, size: 1 },
      ])
      const build = vi.spyOn(roomStore, 'buildRoom')
      const wrapper = render()
      const cell = wrapper.get('[aria-label="Build room at row 1, column 11"]')
      await cell.trigger('mouseenter')
      expect(cell.classes()).toContain('invalid-placement')
      await cell.trigger('click')
      expect(build).not.toHaveBeenCalled()

      const adjacent = wrapper.get('[aria-label="Build room at row 1, column 8"]')
      await adjacent.trigger('mouseenter')
      expect(adjacent.classes()).toContain('valid-placement')
    })

    it.each([
      ['built', 'Diner built successfully!'],
      ['extended', 'Diner extended!'],
    ])('shows the %s toast for a new room', async (result, message) => {
      useAuthStore().token = 'mock-token'
      const roomStore = placing(dinerTemplate, [
        { ...mockRoom, id: 'shaft', name: 'Elevator', coordinate_x: 6, size: 1 },
      ])
      vi.spyOn(roomStore, 'buildRoom').mockResolvedValue(result as never)

      const wrapper = render()
      await wrapper.get('[aria-label="Build room at row 1, column 8"]').trigger('click')
      await wrapper.vm.$nextTick()

      expect(useToast().toasts.value.find((toast) => toast.variant === 'success')?.message).toBe(
        message
      )
    })

    it('keeps the selected room active for repeated Shift-click builds', async () => {
      const roomStore = placing(dinerTemplate, [
        { ...mockRoom, id: 'shaft', name: 'Elevator', coordinate_x: 6, size: 1 },
      ])

      // The first build places a Diner at x=7, which makes the neighbouring
      // slot at x=10 a valid adjacent placement for the repeat build.
      const builtDiner = {
        ...mockRoom,
        id: 'diner-1',
        name: 'Diner',
        category: 'production',
        ability: 'agility',
        coordinate_x: 7,
      }
      const build = vi.spyOn(roomStore, 'buildRoom').mockImplementation(async () => {
        roomStore.rooms = [...roomStore.rooms, builtDiner]
        return 'built'
      })

      const wrapper = render()

      await wrapper.get('[aria-label="Build room at row 1, column 8"]').trigger('click', {
        shiftKey: true,
      })
      await flushPromises()

      await wrapper.get('[aria-label="Build room at row 1, column 11"]').trigger('click', {
        shiftKey: true,
      })
      await flushPromises()

      expect(build).toHaveBeenCalledTimes(2)
      expect(roomStore.selectedRoom).toStrictEqual(dinerTemplate)
      expect(roomStore.isPlacingRoom).toBe(true)
    })

    it('exits placement mode after a normal click build', async () => {
      const roomStore = placing(dinerTemplate, [
        { ...mockRoom, id: 'shaft', name: 'Elevator', coordinate_x: 6, size: 1 },
      ])
      vi.spyOn(roomStore, 'buildRoom').mockResolvedValue('built')

      const wrapper = render()
      await wrapper.get('[aria-label="Build room at row 1, column 8"]').trigger('click')
      await flushPromises()

      expect(roomStore.selectedRoom).toBeNull()
      expect(roomStore.isPlacingRoom).toBe(false)
    })

    it('ignores a second click while a build is still in flight', async () => {
      const roomStore = placing(dinerTemplate, [
        { ...mockRoom, id: 'shaft', name: 'Elevator', coordinate_x: 6, size: 1 },
      ])

      let resolveBuild: ((result: 'built' | 'extended') => void) | undefined
      const build = vi.spyOn(roomStore, 'buildRoom').mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveBuild = resolve
          })
      )

      const wrapper = render()
      const cell = wrapper.get('[aria-label="Build room at row 1, column 8"]')

      // The first placement is still awaiting; a second click on the same cell
      // must not start a parallel build request.
      await cell.trigger('click')
      await cell.trigger('click')

      expect(build).toHaveBeenCalledTimes(1)

      resolveBuild?.('built')
      await flushPromises()
    })
  })

  describe('Training Assignment on Drop', () => {
    const arrangeDrop = (room: Record<string, unknown>, trainingStart?: unknown) => {
      useAuthStore().token = 'mock-token'
      useRoomStore().rooms = [room]
      const assign = vi
        .spyOn(useDwellerStore().management, 'assignDwellerToRoom')
        .mockResolvedValue({ id: 'dweller-123', room_id: room.id, status: 'training' } as any)
      // `null` is an explicit result (a rejected start), not an omitted argument.
      const startTraining =
        trainingStart !== undefined
          ? vi.spyOn(useTrainingStore(), 'startTraining').mockResolvedValue(trainingStart as never)
          : vi.spyOn(useTrainingStore(), 'startTraining')
      return { assign, startTraining }
    }

    it('starts a training session for a dweller dropped into a training room', async () => {
      const { assign, startTraining } = arrangeDrop(trainingRoom, {
        id: 'training-session-123',
        dweller_id: 'dweller-123',
        room_id: 'training-room-123',
        stat_being_trained: 'strength',
        status: 'active',
      })

      await dropOn(render(), 'dweller-123')

      expect(assign).toHaveBeenCalledWith('dweller-123', 'training-room-123')
      expect(startTraining).toHaveBeenCalledWith('dweller-123', 'training-room-123')
    })

    it('does not start training when the dweller lands in a non-training room', async () => {
      const { assign, startTraining } = arrangeDrop(productionRoom)

      await dropOn(render(), 'dweller-123')

      expect(assign).toHaveBeenCalled()
      expect(startTraining).not.toHaveBeenCalled()
    })

    it('survives a training start that returns nothing', async () => {
      const { startTraining } = arrangeDrop(trainingRoom, null)

      await dropOn(render(), 'dweller-123')

      expect(startTraining).toHaveBeenCalled()
      expect(await startTraining.mock.results[0].value).toBeNull()
    })
  })

  describe('Cell rendering', () => {
    it('renders an elevator icon and no info overlay for 1-unit cells', () => {
      const wrapper = renderCell(elevatorRoom)

      expect(wrapper.find('.room-info-overlay').exists()).toBe(false)
      expect(wrapper.find('.small-cell-icon').exists()).toBe(true)
      expect(wrapper.find('.small-cell-icon-svg').exists()).toBe(true)
    })

    it('applies the merge pulse to the upgraded survivor', () => {
      const wrapper = renderCell(mockRoom, { merged: true })

      expect(wrapper.find('.room-merge-pulse').exists()).toBe(true)
    })

    it('renders a compact info overlay for regular 3-unit rooms', () => {
      const wrapper = renderCell(mockRoom)

      expect(wrapper.find('.room-info-overlay').exists()).toBe(true)
      expect(wrapper.find('.small-cell-icon').exists()).toBe(false)
      expect(wrapper.find('.room-name').text()).toBe('Power Generator')
    })

    it('exposes room name and tier as the root accessible name with no native title', () => {
      const wrapper = renderCell({ ...mockRoom, tier: 2 })

      const root = wrapper.find('.built-room')
      expect(root.attributes('aria-label')).toBeUndefined()
      expect(root.text()).toContain('Power Generator')
      expect(root.text()).toContain('T2')
      expect(root.attributes('title')).toBeUndefined()
      // The overlay tooltip conveys the same name and tier.
      expect(wrapper.find('.tooltip-label').text()).toBe('Power Generator (Tier 2)')
    })

    it('conveys the upgrade, destroy and incident tooltip strings', () => {
      const labels = renderCell(
        { ...mockRoom, tier: 1, t2_upgrade_cost: 200 },
        { selected: true, incident }
      )
        .findAll('.tooltip-label')
        .map((label) => label.text())

      expect(labels).toContain('Power Generator (Tier 1)')
      expect(labels).toContain('Upgrade to Tier 2 (200 caps)')
      expect(labels).toContain('Destroy Room')
      expect(labels).toContain('Fight FIRE')
    })
  })

  describe('Apprentice drop gating', () => {
    const dwellerIn = (overrides: Record<string, unknown>) =>
      ({
        first_name: 'X',
        last_name: 'Y',
        room_id: 'production-room-123',
        age_group: 'adult',
        apprentice_stat: null,
        ...overrides,
      }) as any

    const staffedFull = [dwellerIn({ id: 'adult-1' }), dwellerIn({ id: 'adult-2' })]

    const setupDrop = (dwellers: any[], roster: any[] = []) => {
      useAuthStore().token = 'mock-token'
      useRoomStore().rooms = [productionRoom]
      const dwellerStore = useDwellerStore()
      dwellerStore.filter.dwellers = dwellers
      if (roster.length) {
        useVaultStore().activeVaultId = 'vault-1'
        dwellerStore.filter.allDwellers = roster
        dwellerStore.filter.allDwellersLoadedVaultId = 'vault-1'
      }
      return dwellerStore
    }

    const assignSpyFor = (id: string) =>
      vi.spyOn(useDwellerStore().management, 'assignDwellerToRoom').mockResolvedValue({ id } as any)

    it('lets a youth apprentice be dropped on a fully staffed production room', async () => {
      setupDrop([...staffedFull, dwellerIn({ id: 'teen-1', room_id: null, age_group: 'teen' })])
      const assign = assignSpyFor('teen-1')

      await dropOn(render(), 'teen-1')

      expect(assign).toHaveBeenCalledWith('teen-1', 'production-room-123')
    })

    it('admits an apprentice the filter hides when the vault roster has it', async () => {
      const teen = dwellerIn({ id: 'teen-1', room_id: null, age_group: 'teen' })
      setupDrop([...staffedFull], [...staffedFull, teen])
      const assign = assignSpyFor('teen-1')

      await dropOn(render(), 'teen-1')

      expect(assign).toHaveBeenCalledWith('teen-1', 'production-room-123')
    })

    it('still blocks an adult when all worker slots are taken', async () => {
      setupDrop([...staffedFull, dwellerIn({ id: 'adult-3', room_id: null })])
      const assign = assignSpyFor('adult-3')

      await dropOn(render(), 'adult-3')

      expect(assign).not.toHaveBeenCalled()
    })

    it('does not count an apprentice against worker capacity for adults', async () => {
      setupDrop([
        dwellerIn({ id: 'adult-1' }),
        dwellerIn({ id: 'teen-1', age_group: 'teen', apprentice_stat: 'strength' }),
        dwellerIn({ id: 'adult-3', room_id: null }),
      ])
      const assign = assignSpyFor('adult-3')

      await dropOn(render(), 'adult-3')

      expect(assign).toHaveBeenCalledWith('adult-3', 'production-room-123')
    })
  })

  describe('Slot and row geometry', () => {
    it('rejects a regular room preview on the elevator shaft column', async () => {
      placing(dinerTemplate, [])

      const shaftCell = cellAt(render(), 2, 7)
      await shaftCell.trigger('mouseenter')

      expect(shaftCell.classes()).not.toContain('valid-placement')
    })

    it('renders the locked rows below the buildable area', () => {
      expect(render().findAll('.locked-row')).toHaveLength(10)
    })
  })

  describe('Room overlay requests', () => {
    it('opens a room requested before the grid mounted', async () => {
      useRoomStore().rooms = [mockRoom]

      const wrapper = render({ openRoomId: 'room-123' })
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('roomOpened')).toHaveLength(1)
      expect(wrapper.find('[data-testid="room-detail-modal"]').exists()).toBe(true)
    })

    it('keeps a restored dweller above rooms that finish loading later', async () => {
      const roomStore = useRoomStore()
      useRoute().query.dweller = 'dweller-1'
      roomStore.rooms = []
      const wrapper = render({ openRoomId: 'room-123' })
      roomStore.rooms = [mockRoom]
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('roomOpened')).toBeUndefined()

      delete useRoute().query.dweller
      roomStore.rooms = [{ ...mockRoom }]
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('roomOpened')).toHaveLength(1)
      wrapper.unmount()
    })

    it('restores a requested room after its data finishes loading', async () => {
      const roomStore = useRoomStore()
      roomStore.rooms = []
      const wrapper = render({ openRoomId: 'room-123' })
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('roomOpened')).toBeUndefined()

      roomStore.rooms = [mockRoom]
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('roomOpened')).toHaveLength(1)
      wrapper.unmount()
    })
  })
})
