import axios from '@/core/plugins/axios'
import type { ConnectionRead, UserBlockRead } from '../models/messages'

async function inviteByUsername(username: string, token: string): Promise<ConnectionRead> {
  const response = await axios.post<ConnectionRead>(
    '/api/v1/connections',
    { username },
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

async function acceptConnection(connectionId: string, token: string): Promise<ConnectionRead> {
  const response = await axios.post<ConnectionRead>(
    `/api/v1/connections/${connectionId}/accept`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

async function declineConnection(connectionId: string, token: string): Promise<void> {
  await axios.post(`/api/v1/connections/${connectionId}/decline`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

async function revokeConnection(connectionId: string, token: string): Promise<void> {
  await axios.delete(`/api/v1/connections/${connectionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

async function listConnections(token: string): Promise<ConnectionRead[]> {
  const response = await axios.get<ConnectionRead[]>('/api/v1/connections', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function blockUser(userId: string, token: string): Promise<UserBlockRead> {
  const response = await axios.post<UserBlockRead>(`/api/v1/blocks/${userId}`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function unblockUser(userId: string, token: string): Promise<void> {
  await axios.delete(`/api/v1/blocks/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

async function listBlocks(token: string): Promise<UserBlockRead[]> {
  const response = await axios.get<UserBlockRead[]>('/api/v1/blocks', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export const messagesService = {
  inviteByUsername,
  acceptConnection,
  declineConnection,
  revokeConnection,
  listConnections,
  blockUser,
  unblockUser,
  listBlocks,
}