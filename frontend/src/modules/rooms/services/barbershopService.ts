import axios from '@/core/plugins/axios'
import type {
  BarbershopChangeRequest,
  BarbershopChangeResponse,
  BarbershopStatus,
} from '../models/barbershop'

function requestConfig(token: string) {
  return {
    headers: { Authorization: `Bearer ${token}` },
    _skipErrorNotification: true as const,
  }
}

export async function fetchBarbershopStatus(
  roomId: string,
  token: string
): Promise<BarbershopStatus> {
  const response = await axios.get<BarbershopStatus>(
    `/api/v1/rooms/${roomId}/barbershop`,
    requestConfig(token)
  )
  return response.data
}

export async function changeBarbershopAppearance(
  roomId: string,
  dwellerId: string,
  payload: BarbershopChangeRequest,
  token: string
): Promise<BarbershopChangeResponse> {
  const response = await axios.post<BarbershopChangeResponse>(
    `/api/v1/rooms/${roomId}/barbershop/dwellers/${dwellerId}`,
    payload,
    requestConfig(token)
  )
  return response.data
}
