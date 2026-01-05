import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import { useRoomStore } from '@/stores/room'

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
})
