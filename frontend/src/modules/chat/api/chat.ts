import { apiGet, apiPost } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type ChatMessageRead = components['schemas']['ChatMessageRead']
export type DwellerChatResponse = components['schemas']['DwellerChatResponse']
export type DwellerVoiceChatResponse = components['schemas']['DwellerVoiceChatResponse']

/** Action suggestion as delivered on the wire (may include types the chat UI ignores). */
export type ChatActionSuggestion = NonNullable<DwellerChatResponse['action_suggestion']>

export interface ChatHistoryParams {
  offset?: number
  limit?: number
}

/** Chat transport boundary; Bearer auth is injected by the shared API interceptor. */
export const chatApi = {
  getHistory(dwellerId: string, params?: ChatHistoryParams): Promise<ChatMessageRead[]> {
    const url = `/api/v1/chat/history/${dwellerId}`
    return params
      ? apiGet<ChatMessageRead[]>(url, {
          params: { offset: params.offset, limit: params.limit },
        })
      : apiGet<ChatMessageRead[]>(url)
  },

  sendMessage(
    dwellerId: string,
    message: string,
    options: { debug?: boolean } = {}
  ): Promise<DwellerChatResponse> {
    return apiPost<DwellerChatResponse>(
      `/api/v1/chat/${dwellerId}`,
      { message },
      { params: { debug: options.debug ? true : undefined } }
    )
  },

  sendVoiceMessage(
    dwellerId: string,
    audioFile: Blob,
    options: { returnAudio?: boolean } = {}
  ): Promise<DwellerVoiceChatResponse> {
    const formData = new FormData()
    formData.append('audio_file', audioFile, 'recording.webm')
    // Override the shared JSON default; the browser adapter supplies the multipart boundary.
    return apiPost<DwellerVoiceChatResponse>(`/api/v1/chat/${dwellerId}/voice`, formData, {
      params: { return_audio: options.returnAudio ?? false },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
