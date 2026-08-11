import { describe, expect, it, vi } from 'vitest'
import { useAsyncAction } from '@/core/composables/useAsyncAction'

const toast = vi.hoisted(() => ({ error: vi.fn() }))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ error: toast.error }),
}))

describe('useAsyncAction', () => {
  it('tracks loading and returns the action result', async () => {
    let resolveAction!: (value: string) => void
    const action = vi.fn(
      () => new Promise<string>((resolve) => {
        resolveAction = resolve
      })
    )
    const { run, isLoading } = useAsyncAction(action)

    const result = run()
    expect(isLoading.value).toBe(true)
    resolveAction('complete')

    await expect(result).resolves.toBe('complete')
    expect(isLoading.value).toBe(false)
  })

  it('returns null and surfaces a toast by default', async () => {
    const { run, error } = useAsyncAction(async () => {
      throw new Error('offline')
    })

    await expect(run()).resolves.toBeNull()
    expect(error.value).toBe('offline')
    expect(toast.error).toHaveBeenCalledWith('offline')
  })

  it('rethrows after recording an error when requested', async () => {
    const failure = new Error('required by caller')
    const { run, error } = useAsyncAction(
      async () => {
        throw failure
      },
      { rethrow: true, showToast: false }
    )

    await expect(run()).rejects.toThrow(failure)
    expect(error.value).toBe('required by caller')
  })
})
