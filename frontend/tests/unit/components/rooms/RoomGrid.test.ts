import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import { useRoomStore } from '@/stores/room'
import { useDwellerStore } from '@/stores/dweller'
import { useTrainingStore } from '@/stores/training'
import { useAuthStore } from '@/stores/auth'

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
    capacity: 6
  }

  describe('Room Highlighting', () => {
    it('should apply highlighted class when highlightedRoomId matches room id', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123',
          incidents: []
        }
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
          incidents: []
        }
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
          incidents: []
        }
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
          coordinate_y: 0
        }
      ]

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123', // Only first room should be highlighted
          incidents: []
        }
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
        severity: 'medium'
      }

      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: 'room-123',
          incidents: [mockIncident] as any
        }
      })

      const builtRoom = wrapper.find('.built-room')
      expect(builtRoom.classes()).toContain('highlighted')
      expect(builtRoom.classes()).toContain('has-incident')
    })
  })

  describe('Room Grid Structure', () => {
    it('should render room grid container', () => {
      const wrapper = mount(RoomGrid, {
        props: {
          incidents: []
        }
      })

      const grid = wrapper.find('.room-grid')
      expect(grid.exists()).toBe(true)
    })

    it('should render built rooms with correct styling', () => {
      const roomStore = useRoomStore()
      roomStore.rooms = [mockRoom]

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: []
        }
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
          incidents: []
        }
      })

      expect(wrapper.props('highlightedRoomId')).toBe('room-123')
    })

    it('should accept highlightedRoomId as null', () => {
      const wrapper = mount(RoomGrid, {
        props: {
          highlightedRoomId: null,
          incidents: []
        }
      })

      expect(wrapper.props('highlightedRoomId')).toBeNull()
    })
  })

  describe('Training Assignment on Drop', () => {
    it('should start training session when dweller is dropped into training room', async () => {
      const roomStore = useRoomStore()
      const dwellerStore = useDwellerStore()
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
        capacity: 6
      }
      roomStore.rooms = [trainingRoom]

      // Mock store methods
      const assignDwellerSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'training-room-123',
        status: 'training'
      } as any)

      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining').mockResolvedValue({
        id: 'training-session-123',
        dweller_id: 'dweller-123',
        room_id: 'training-room-123',
        stat_being_trained: 'strength',
        status: 'active'
      } as any)

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: []
        }
      })

      // Simulate drop event with JSON data
      const dropEvent = {
        preventDefault: vi.fn(),
        dataTransfer: {
          getData: vi.fn((type: string) => {
            if (type === 'application/json') {
              return JSON.stringify({
                dwellerId: 'dweller-123',
                firstName: 'John',
                lastName: 'Doe',
                currentRoomId: null
              })
            }
            return ''
          })
        }
      }

      const roomElement = wrapper.find('.built-room')
      await roomElement.trigger('drop', dropEvent as any)

      // Wait for async operations
      await wrapper.vm.$nextTick()

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
      const dwellerStore = useDwellerStore()
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
        capacity: 6
      }
      roomStore.rooms = [productionRoom]

      const assignDwellerSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'production-room-123',
        status: 'working'
      } as any)

      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining')

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: []
        }
      })

      // Simulate drop event with JSON data
      const dropEvent = {
        preventDefault: vi.fn(),
        dataTransfer: {
          getData: vi.fn((type: string) => {
            if (type === 'application/json') {
              return JSON.stringify({
                dwellerId: 'dweller-123',
                firstName: 'John',
                lastName: 'Doe',
                currentRoomId: null
              })
            }
            return ''
          })
        }
      }

      const roomElement = wrapper.find('.built-room')
      await roomElement.trigger('drop', dropEvent as any)
      await wrapper.vm.$nextTick()

      // Verify assignDwellerToRoom was called
      expect(assignDwellerSpy).toHaveBeenCalled()

      // Verify startTraining was NOT called for non-training room
      expect(startTrainingSpy).not.toHaveBeenCalled()
    })

    it('should handle training start failure gracefully', async () => {
      const roomStore = useRoomStore()
      const dwellerStore = useDwellerStore()
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
        capacity: 6
      }
      roomStore.rooms = [trainingRoom]

      vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({
        id: 'dweller-123',
        first_name: 'John',
        last_name: 'Doe',
        room_id: 'training-room-123',
        status: 'training'
      } as any)

      // Mock training start to fail
      const startTrainingSpy = vi.spyOn(trainingStore, 'startTraining').mockResolvedValue(null)

      const wrapper = mount(RoomGrid, {
        props: {
          incidents: []
        }
      })

      const dropEvent = {
        preventDefault: vi.fn(),
        dataTransfer: {
          getData: vi.fn((type: string) => {
            if (type === 'application/json') {
              return JSON.stringify({
                dwellerId: 'dweller-123',
                firstName: 'John',
                lastName: 'Doe',
                currentRoomId: null
              })
            }
            return ''
          })
        }
      }

      const roomElement = wrapper.find('.built-room')
      await roomElement.trigger('drop', dropEvent as any)
      await wrapper.vm.$nextTick()

      // Verify startTraining was called and returned null (failure)
      expect(startTrainingSpy).toHaveBeenCalled()
      expect(await startTrainingSpy.mock.results[0].value).toBeNull()
    })
  })
})
