import { describe, expect, it } from 'vitest'
import { getErrorMessage } from '@/core/types/utils'

describe('getErrorMessage', () => {
  it('uses the caller fallback when an Axios-like response has no data', () => {
    expect(getErrorMessage({ response: { status: 500 } }, 'Audio upload failed')).toBe(
      'Audio upload failed'
    )
  })
})
