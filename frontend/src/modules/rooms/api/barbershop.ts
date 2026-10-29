import { apiGet, apiPost } from '@/core/utils/api'
import type {
  BarbershopChangeRequest,
  BarbershopChangeResponse,
  BarbershopStatus,
} from '../models/barbershop'

export const barbershopApi = {
  getStatus: (roomId: string) =>
    apiGet<BarbershopStatus>(`/api/v1/rooms/${roomId}/barbershop`, {
      skipErrorNotification: true,
    }),

  changeAppearance: (roomId: string, dwellerId: string, payload: BarbershopChangeRequest) =>
    apiPost<BarbershopChangeResponse>(
      `/api/v1/rooms/${roomId}/barbershop/dwellers/${dwellerId}`,
      payload,
      { skipErrorNotification: true }
    ),
}
