import { api, apiGet, apiPost } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'
import type {
  Room,
  RoomBuild,
  RoomRushQuote,
  RoomRushResult,
  RoomStyleValue,
  RoomTemplate,
} from '../models/room'

type GridConfig = components['schemas']['GridConfig']

export const roomApi = {
  getByVault: (vaultId: string, limit: number) =>
    apiGet<Room[]>(`/api/v1/rooms/vault/${vaultId}/`, { params: { limit } }),

  getBuildable: (vaultId: string) => apiGet<RoomTemplate[]>(`/api/v1/rooms/buildable/${vaultId}/`),

  build: (data: RoomBuild) => apiPost<Room>('/api/v1/rooms/build/', data),

  destroy: (roomId: string) => api.delete<void>(`/api/v1/rooms/destroy/${roomId}`),

  upgrade: (roomId: string) => apiPost<Room>(`/api/v1/rooms/upgrade/${roomId}`, {}),

  remodel: (roomId: string, otherRoomId?: string) => {
    const action = otherRoomId ? 'merge' : 'split'
    return apiPost<Room | Room[]>(
      `/api/v1/rooms/${action}/${roomId}`,
      otherRoomId ? { other_room_id: otherRoomId } : {}
    )
  },

  applyStyle: (roomId: string, style: RoomStyleValue) =>
    apiPost<Room>(`/api/v1/rooms/style/${roomId}`, { style }),

  getGridConfig: () => apiGet<GridConfig>('/api/v1/rooms/grid-config/'),

  getRushQuote: (roomId: string) => apiGet<RoomRushQuote>(`/api/v1/rooms/${roomId}/rush`),

  rush: (roomId: string) => apiPost<RoomRushResult>(`/api/v1/rooms/${roomId}/rush`, {}),
}
