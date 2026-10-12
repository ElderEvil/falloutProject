import axios from '@/core/plugins/axios'
import type { ConnectionRead, DirectMessageRead, DirectMessageSummary, UserBlockRead } from '../models/messages'

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

async function sendMessage(userId: string, body: string, token: string): Promise<DirectMessageRead> {
  const response = await axios.post<DirectMessageRead>(
    `/api/v1/messages/${userId}`,
    { body },
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

async function getThread(
  userId: string,
  token: string,
  limit = 50,
  offset = 0
): Promise<DirectMessageRead[]> {
  const response = await axios.get<DirectMessageRead[]>(`/api/v1/messages/${userId}`, {
    params: { limit, offset },
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function listConversations(token: string, limit = 50): Promise<DirectMessageSummary[]> {
  const response = await axios.get<DirectMessageSummary[]>('/api/v1/messages', {
    params: { limit },
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function acceptMessageRequest(userId: string, token: string): Promise<ConnectionRead> {
  const response = await axios.post<ConnectionRead>(`/api/v1/messages/${userId}/accept`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function declineMessageRequest(userId: string, token: string): Promise<void> {
  await axios.post(`/api/v1/messages/${userId}/decline`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
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
  sendMessage,
  getThread,
  listConversations,
  acceptMessageRequest,
  declineMessageRequest,
}