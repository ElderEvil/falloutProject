import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RoomGrid from '@/modules/rooms/components/RoomGrid.vue'
import RoomGridCell from '@/modules/rooms/components/RoomGridCell.vue'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'

describe('RoomGrid', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

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

  const dropEventFor = (dwellerId: string) => ({
    preventDefault: vi.fn(),
    dataTransfer: {
      getData: vi.fn(() =>
        JSON.stringify({ dwellerId, firstName: 'X', lastName: 'Y', currentRoomId: null })
      ),
    },
  })

  const dropOn = async (wrapper: ReturnType<typeof mount>, dwellerId: string) => {
    await wrapper.find('.built-room').trigger('drop', dropEventFor(dwellerId) as any)
    await wrapper.vm.$nextTick()
  }

  describe('Room Highlighting', () => {
    it('shows an attention count only on the Overseer’s Office', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [
        { ...mockRoom, id: 'office-123', name: "Overseer's Office" },
        mockRoom,
      ]

      const wrapper = mount(RoomGrid, {
        props: { incidents: [], overseerAttentionCount: 3 },
      })

      expect(wrapper.findAll('.overseer-alert-badge')).toHaveLength(1)
      expect(wrapper.find('.overseer-alert-badge').text()).toBe('3 items need attention')
    })

    it('does not show an attention count on other rooms', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: { incidents: [], overseerAttentionCount: 3 },
      })

      expect(wrapper.find('.overseer-alert-badge').exists()).toBe(false)
    })

    it('should apply highlighted class when highlightedRoomId matches room id', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123',
          incidents: [],
        },
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.classes()).toContain('highlighted')
    })

    it('should not apply highlighted class when highlightedRoomId is different', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'different-room-id',
          incidents: [],
        },
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.classes()).not.toContain('highlighted')
    })

    it('should not apply highlighted class when highlightedRoomId is null', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: null,
          incidents: [],
        },
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.classes()).not.toContain('highlighted')
    })
  })

  describe('Multiple Rooms', () => {
    it('should only highlight the specific room when multiple rooms exist', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [
        mockRoom,
        {
          ...mockRoom,
          id: 'room-456',
          name: 'Diner',
          coordinate_x: 1,
          coordinate_y: 0,
        },
      ]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123', // Only first room should be highlighted
          incidents: [],
        },
      })

      const builtRooms = wrapper.findAll('.built-room')
      expect(builtRooms).toHaveLength(2)

      // First room should be highlighted
      expect(builtRooms[0].classes()).toContain('highlighted')

      // Second room should not be highlighted
      expect(builtRooms[1].classes()).not.toContain('highlighted')
    })
  })

  describe('Highlight with Incidents', () => {
    it('should apply both highlighted and has-incident classes when room has both', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const mockIncident = {
        id: 'incident-1',
        room_id: 'room-123',
        type: 'FIRE',
        severity: 'medium',
      }

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123',
          incidents: [mockIncident] as any,
        },
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.classes()).toContain('highlighted')
      expect(builtRoom.classes()).toContain('has-incident')
    })

    it.each(['enter', 'space'] as const)(
      'does not emit the room click when %s activates the incident badge',
      async (key) => {
        const mockIncident = {
          id: 'incident-1',
          room_id: 'room-123',
          type: 'FIRE',
          severity: 'medium',
        }

        const wrapper = mount(RoomGridCell, {
          props: {
            room: mockRoom,
            showRoomImages: true,
            isPowerOutage: false,
            selected: false,
            isDraggingOver: false,
            highlighted: false,
            incident: mockIncident as any,
          },
        })

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
      const roomStore = useRoomStore()
      // mockRoom sits on row 0 (door-anchored); no elevator on row 1+ means
      // those levels are locked
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })

      const rows = wrapper.findAll('.empty').map((c) => (c.element as HTMLElement).style.gridRow)
      // Cells render on every level
      expect(rows.length).toBeGreaterThan(8)
      // Only row 0 is unlocked
      const unlocked = wrapper.findAll('.empty:not(.level-locked)')
      const unlockedRows = unlocked.map((c) => (c.element as HTMLElement).style.gridRow)
      expect(unlockedRows.every((r) => r === '1')).toBe(true)
    })

    it('unlocks a level when an elevator is built on it', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [
        mockRoom,
        { ...mockRoom, id: 'elev-1', name: 'Elevator', coordinate_x: 0, coordinate_y: 3 },
      ]

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })

      const unlockedRows = wrapper
        .findAll('.empty:not(.level-locked)')
        .map((c) => (c.element as HTMLElement).style.gridRow)
      expect(unlockedRows).toContain('4')
    })

    it('allows a standard room beside a legacy-size elevator on the same level', async () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [
        mockRoom,
        { ...mockRoom, id: 'elev-1', name: 'Elevator', coordinate_x: 0, coordinate_y: 1, size_min: 1 },
      ]
      roomStore.selectedRoom = {
        name: 'Diner',
        category: 'production',
        ability: 'agility',
        base_cost: 100,
        t2_upgrade_cost: 200,
        t3_upgrade_cost: 400,
        size_min: 3,
        size_max: 9,
        tier: 1,
        speedup_multiplier: 1,
      }
      roomStore.isPlacingRoom = true

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })
      const cell = wrapper
        .findAll('.empty:not(.level-locked)')
        .find((item) => {
          const style = item.element as HTMLElement
          return style.style.gridColumn === '2' && style.style.gridRow === '2'
        })!

      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('valid-placement')
    })

    it('marks an elevator preview as invalid when there is no elevator above', async () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]
      roomStore.selectedRoom = {
        name: 'Elevator',
        category: 'misc',
        ability: null,
        base_cost: 100,
        t2_upgrade_cost: null,
        t3_upgrade_cost: null,
        size_min: 1,
        size_max: 1,
        tier: 1,
        speedup_multiplier: 1,
      }
      roomStore.isPlacingRoom = true

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })

      const cell = wrapper.findAll('.empty:not(.level-locked)')[1]
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('invalid-placement')
    })

    it('allows an elevator preview on a locked level when stacked under one', async () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [
        mockRoom,
        { ...mockRoom, id: 'elev-1', name: 'Elevator', coordinate_x: 0, coordinate_y: 3 },
      ]
      roomStore.selectedRoom = {
        name: 'Elevator',
        category: 'misc',
        ability: null,
        base_cost: 100,
        t2_upgrade_cost: null,
        t3_upgrade_cost: null,
        size_min: 1,
        size_max: 1,
        tier: 1,
        speedup_multiplier: 1,
      }
      roomStore.isPlacingRoom = true

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })

      // Level 4 has no elevator (locked) but is directly below the level-3
      // elevator, so an elevator preview there must be valid. While placing
      // an elevator the locked styling is lifted so the cell is interactive.
      const cell = wrapper.findAll('.empty').find((c) => (c.element as HTMLElement).style.gridRow === '5')!
      expect(cell.classes()).not.toContain('level-locked')
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('hover-preview')
      expect(cell.classes()).toContain('valid-placement')
    })

    it('marks a non-elevator preview as invalid on a level without an elevator', async () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]
      roomStore.selectedRoom = {
        name: 'Diner',
        category: 'production',
        ability: 'agility',
        base_cost: 100,
        t2_upgrade_cost: 200,
        t3_upgrade_cost: 400,
        size_min: 3,
        size_max: 9,
        tier: 1,
        speedup_multiplier: 1,
      }
      roomStore.isPlacingRoom = true

      const wrapper = mount(RoomGrid, {
        props: { incidents: [] },
      })

      // Hover the first cell on a locked level (row 1+, no elevator)
      const cell = wrapper.findAll('.empty.level-locked')[0]!
      await cell.trigger('mouseenter')

      expect(cell.classes()).toContain('level-locked')
      expect(cell.classes()).not.toContain('hover-preview')
    })
  })

  describe('Room Grid Structure', () => {
    it('should render room grid container', () => {
      const wrapper = mount(RoomGrid, {
        props: {
          incidents: [],
        },
      })

      const grid = wrapper.find('.room-grid')
      expect(grid.exists()).toBe(true)
    })

    it('should render built rooms with correct styling', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: [],
        },
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.exists()).toBe(true)
      expect(builtRoom.classes()).toContain('room')
    })
  })

  describe('Prop Validation', () => {
    it('should accept highlightedRoomId as string', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123',
          incidents: [],
        },
      })

      expect(wrapper.props('highlightedRoomId')).toBe('room-123')
    })

    it('should accept highlightedRoomId as null', () => {
      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: null,
          incidents: [],
        },
      })

      expect(wrapper.props('highlightedRoomId')).toBeNull()
    })
  })

  describe('Training Assignment on Drop', () => {
    it('should start training session when dweller is dropped into training room', async () => {
      const roomStore = useRoomStore()
      const dwellerStore = useDwellerStore().management
      const trainingStore = useTrainingStore()
      const authStore = useAuthStore()

      // Mock auth token
      authStore.token = 'mock-token'

      // Setup training room
      const trainingRoom = {
        id: 'training-room-123',
        name: 'Weight Room',
        category: 'training',
        ability: 'strength',
        coordinate_x: 0,
        coordinate_y: 0,
        size: 3,
        size_min: 3,
        tier: 1,
        capacity: 6,
      }
      roomStore.rooms = [trainingRoom]

      // Mock store methods
      const assignDwellerSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'training-room-123',
        status: 'training',
      } as any)

      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining').mockResolvedValue({
        id: 'training-session-123',
        dweller_id: 'dweller-123',
        room_id: 'training-room-123',
        stat_being_trained: 'strength',
        status: 'active',
      } as any)

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: [],
        },
      })
      await dropOn(wrapper, 'dweller-123')

      // Verify assignDwellerToRoom was called
      expect(assignDwellerSpy).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-123',
        'mock-token'
      )

      // Verify startTraining was called after assignment
      expect(startTrainingSpy).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-123',
        'mock-token'
      )
    })

    it('should not start training session when dropped into non-training room', async () => {
      const roomStore = useRoomStore()
      const dwellerStore = useDwellerStore().management
      const trainingStore = useTrainingStore()
      const authStore = useAuthStore()

      authStore.token = 'mock-token'

      // Setup production room (not training)
      const productionRoom = {
        id: 'production-room-123',
        name: 'Power Generator',
        category: 'production',
        ability: 'strength',
        coordinate_x: 0,
        coordinate_y: 0,
        size: 3,
        size_min: 3,
        tier: 1,
        capacity: 6,
      }
      roomStore.rooms = [productionRoom]

      const assignDwellerSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'production-room-123',
        status: 'working',
      } as any)

      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining')

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: [],
        },
      })
      await dropOn(wrapper, 'dweller-123')

      // Verify assignDwellerToRoom was called
      expect(assignDwellerSpy).toHaveBeenCalled()

      // Verify startTraining was NOT called for non-training room
      expect(startTrainingSpy).not.toHaveBeenCalled()
    })

    it('should handle training start failure gracefully', async () => {
      const roomStore = useRoomStore()
      const dwellerStore = useDwellerStore().management
      const trainingStore = useTrainingStore()
      const authStore = useAuthStore()

      authStore.token = 'mock-token'

      const trainingRoom = {
        id: 'training-room-123',
        name: 'Weight Room',
        category: 'training',
        ability: 'strength',
        coordinate_x: 0,
        coordinate_y: 0,
        size: 3,
        size_min: 3,
        tier: 1,
        capacity: 6,
      }
      roomStore.rooms = [trainingRoom]

      vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'training-room-123',
        status: 'training',
      } as any)

      // Mock training start to fail
      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining').mockResolvedValue(null)

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: [],
        },
      })
      await dropOn(wrapper, 'dweller-123')

      // Verify startTraining was called and returned null (failure)
      expect(startTrainingSpy).toHaveBeenCalled()
      expect(await startTrainingSpy.mock.results[0].value).toBeNull()
    })
  })

  describe('Apprentice drop gating', () => {
    const productionRoom = {
      id: 'production-room-123',
      name: 'Power Generator',
      category: 'production',
      ability: 'strength',
      coordinate_x: 0,
      coordinate_y: 0,
      size: 3,
      size_min: 3,
      tier: 1,
      capacity: 6,
    }

    const dwellerIn = (overrides: Record<string, unknown>) =>
      ({
        first_name: 'X',
        last_name: 'Y',
        room_id: 'production-room-123',
        is_adult: true,
        apprentice_stat: null,
        ...overrides,
      }) as any

    const staffedFull = [dwellerIn({ id: 'adult-1' }), dwellerIn({ id: 'adult-2' })]

    const setupDrop = (dwellers: any[]) => {
      useAuthStore().token = 'mock-token'
      useRoomStore().rooms = [productionRoom]
      const dwellerStore = useDwellerStore()
      dwellerStore.filter.dwellers = dwellers
      return dwellerStore
    }

    it('lets a youth apprentice be dropped on a fully staffed production room', async () => {
      const dwellerStore = setupDrop([
        ...staffedFull,
        dwellerIn({ id: 'teen-1', room_id: null, is_adult: false, age_group: 'teen' }),
      ])

      const assignSpy = vi
        .spyOn(dwellerStore.management, 'assignDwellerToRoom')
        .mockResolvedValue({ id: 'teen-1' } as any)

      const wrapper = mount(RoomGrid, { props: { incidents: [] } })
      await dropOn(wrapper, 'teen-1')

      expect(assignSpy).toHaveBeenCalledWith('teen-1', 'production-room-123', 'mock-token')
    })

    it('still blocks an adult when all worker slots are taken', async () => {
      const dwellerStore = setupDrop([
        ...staffedFull,
        dwellerIn({ id: 'adult-3', room_id: null }),
      ])

      const assignSpy = vi
        .spyOn(dwellerStore.management, 'assignDwellerToRoom')
        .mockResolvedValue({ id: 'adult-3' } as any)

      const wrapper = mount(RoomGrid, { props: { incidents: [] } })
      await dropOn(wrapper, 'adult-3')

      expect(assignSpy).not.toHaveBeenCalled()
    })

    it('does not count an apprentice against worker capacity for adults', async () => {
      const dwellerStore = setupDrop([
        dwellerIn({ id: 'adult-1' }),
        dwellerIn({ id: 'teen-1', is_adult: false, age_group: 'teen', apprentice_stat: 'strength' }),
        dwellerIn({ id: 'adult-3', room_id: null }),
      ])

      const assignSpy = vi
        .spyOn(dwellerStore.management, 'assignDwellerToRoom')
        .mockResolvedValue({ id: 'adult-3' } as any)

      const wrapper = mount(RoomGrid, { props: { incidents: [] } })
      await dropOn(wrapper, 'adult-3')

      expect(assignSpy).toHaveBeenCalledWith('adult-3', 'production-room-123', 'mock-token')
    })
  })
})
