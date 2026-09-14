import { describe, expect, it } from 'vitest'
import { useChatMessages } from '@/modules/chat/composables/useChatMessages'

describe('useChatMessages avatar URL', () => {
  it('uses the API origin for backend static avatars', () => {
    const { dwellerAvatarUrl } = useChatMessages({
      dwellerId: 'dweller-1',
      dwellerAvatar: '/static/legendary_dweller_images/FOS_Dw_Butch.png',
      token: null,
    })

    expect(dwellerAvatarUrl.value).toBe(
      'http://localhost:8000/static/legendary_dweller_images/FOS_Dw_Butch.png'
    )
  })

  it('passes absolute avatar URLs through unchanged', () => {
    const { dwellerAvatarUrl } = useChatMessages({
      dwellerId: 'dweller-1',
      dwellerAvatar: 'https://s3-api.example.com/dweller-images/photo.png',
      token: null,
    })

    expect(dwellerAvatarUrl.value).toBe('https://s3-api.example.com/dweller-images/photo.png')
  })
})
