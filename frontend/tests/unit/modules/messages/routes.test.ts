import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import router from '@/router'

describe('Messages route', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('registers /vault/:id/messages with requiresAuth', () => {
    const resolved = router.resolve('/vault/abc/messages')
    expect(resolved.name).toBe('messages')
    expect(resolved.meta.requiresAuth).toBe(true)
    expect(resolved.meta.parentRoute).toBe('/vault/:id')
  })
})