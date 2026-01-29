import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useToast } from '@/core/composables/useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    const { toasts, remove } = useToast()
    toasts.value.forEach((t) => remove(t.id))
  })

  describe('basic toast creation', () => {
    it('should create a toast with default info variant', () => {
      const { show, toasts } = useToast()
      show('Test message')

      expect(toasts.value).toHaveLength(1)
      expect(toasts.value[0]).toMatchObject({
        message: 'Test message',
        variant: 'info',
        count: 1,
      })
    })

    it('should create a toast with specified variant', () => {
      const { show, toasts } = useToast()
      show('Error occurred', 'error')

      expect(toasts.value[0].variant).toBe('error')
    })

    it('should return unique toast id', () => {
      const { show } = useToast()
      const id1 = show('Message 1')
      const id2 = show('Message 2')

      expect(id1).not.toBe(id2)
      expect(id1).toMatch(/^toast-\d+$/)
    })
  })

  describe('default durations', () => {
    it('should use default duration for success (3000ms)', () => {
      const { success, toasts } = useToast()
      success('Success message')

      expect(toasts.value[0].duration).toBe(3000)
    })

    it('should use default duration for info (5000ms)', () => {
      const { info, toasts } = useToast()
      info('Info message')

      expect(toasts.value[0].duration).toBe(5000)
    })

    it('should use default duration for warning (7000ms)', () => {
      const { warning, toasts } = useToast()
      warning('Warning message')

      expect(toasts.value[0].duration).toBe(7000)
    })

    it('should use default duration for error (0 - persistent)', () => {
      const { error, toasts } = useToast()
      error('Error message')

      expect(toasts.value[0].duration).toBe(0)
    })

    it('should override default duration with explicit value', () => {
      const { success, toasts } = useToast()
      success('Success message', 1000)

      expect(toasts.value[0].duration).toBe(1000)
    })
  })

  describe('auto-dismiss behavior', () => {
    it('should auto-dismiss toast after duration', () => {
      const { show, toasts } = useToast()
      show('Test message', 'info', 5000)

      expect(toasts.value).toHaveLength(1)

      vi.advanceTimersByTime(5000)

      expect(toasts.value).toHaveLength(0)
    })

    it('should not auto-dismiss toast with duration 0', () => {
      const { error, toasts } = useToast()
      error('Persistent error')

      expect(toasts.value).toHaveLength(1)

      vi.advanceTimersByTime(10000)

      expect(toasts.value).toHaveLength(1)
    })

    it('should not auto-dismiss toast with negative duration', () => {
      const { show, toasts } = useToast()
      show('Test message', 'info', -1)

      expect(toasts.value).toHaveLength(1)

      vi.advanceTimersByTime(10000)

      expect(toasts.value).toHaveLength(1)
    })
  })

  describe('toast grouping', () => {
    it('should group duplicate toasts by variant and message', () => {
      const { show, toasts } = useToast()
      const id1 = show('Duplicate message', 'success')
      const id2 = show('Duplicate message', 'success')

      expect(toasts.value).toHaveLength(1)
      expect(id1).toBe(id2)
      expect(toasts.value[0].count).toBe(2)
    })

    it('should not group toasts with different messages', () => {
      const { show, toasts } = useToast()
      show('Message 1', 'success')
      show('Message 2', 'success')

      expect(toasts.value).toHaveLength(2)
    })

    it('should not group toasts with different variants', () => {
      const { show, toasts } = useToast()
      show('Same message', 'success')
      show('Same message', 'error')

      expect(toasts.value).toHaveLength(2)
    })

    it('should increment count on duplicate toast', () => {
      const { show, toasts } = useToast()
      show('Duplicate', 'info')
      show('Duplicate', 'info')
      show('Duplicate', 'info')

      expect(toasts.value).toHaveLength(1)
      expect(toasts.value[0].count).toBe(3)
    })
  })

  describe('timeout refresh on duplicate', () => {
    it('should refresh timeout when duplicate toast arrives', () => {
      const { show, toasts } = useToast()
      show('Message', 'info', 5000)

      vi.advanceTimersByTime(3000)
      expect(toasts.value).toHaveLength(1)

      show('Message', 'info', 5000)

      vi.advanceTimersByTime(3000)
      expect(toasts.value).toHaveLength(1)

      vi.advanceTimersByTime(2000)
      expect(toasts.value).toHaveLength(0)
    })

    it('should use new duration when duplicate arrives with different duration', () => {
      const { show, toasts } = useToast()
      show('Message', 'info', 5000)

      vi.advanceTimersByTime(3000)

      show('Message', 'info', 2000)

      vi.advanceTimersByTime(2000)
      expect(toasts.value).toHaveLength(0)
    })

    it('should clear timeout when duplicate has duration 0', () => {
      const { show, toasts } = useToast()
      show('Message', 'info', 5000)

      vi.advanceTimersByTime(3000)

      show('Message', 'info', 0)

      vi.advanceTimersByTime(10000)
      expect(toasts.value).toHaveLength(1)
    })
  })

  describe('MAX_TOASTS behavior', () => {
    it('should remove oldest toast when limit reached with new unique toast', () => {
      const { show, toasts } = useToast()
      show('Toast 1', 'info')
      show('Toast 2', 'info')
      show('Toast 3', 'info')
      show('Toast 4', 'info')
      show('Toast 5', 'info')

      expect(toasts.value).toHaveLength(5)

      show('Toast 6', 'info')

      expect(toasts.value).toHaveLength(5)
      expect(toasts.value[0].message).toBe('Toast 2')
    })

    it('should not evict when duplicate arrives at max capacity', () => {
      const { show, toasts } = useToast()
      show('Toast 1', 'info')
      show('Toast 2', 'info')
      show('Toast 3', 'info')
      show('Toast 4', 'info')
      show('Toast 5', 'info')

      expect(toasts.value).toHaveLength(5)

      show('Toast 1', 'info')

      expect(toasts.value).toHaveLength(5)
      expect(toasts.value[0].count).toBe(2)
    })
  })

  describe('remove function', () => {
    it('should remove toast by id', () => {
      const { show, remove, toasts } = useToast()
      const id = show('Test message')

      expect(toasts.value).toHaveLength(1)

      remove(id)

      expect(toasts.value).toHaveLength(0)
    })

    it('should clear timeout when removing toast', () => {
      const { show, remove, toasts } = useToast()
      const id = show('Test message', 'info', 5000)

      vi.advanceTimersByTime(2000)

      remove(id)

      vi.advanceTimersByTime(5000)

      expect(toasts.value).toHaveLength(0)
    })

    it('should not throw when removing non-existent toast', () => {
      const { remove } = useToast()

      expect(() => {
        remove('non-existent-id')
      }).not.toThrow()
    })
  })

  describe('convenience methods', () => {
    it('should create success toast', () => {
      const { success, toasts } = useToast()
      success('Success!')

      expect(toasts.value[0].variant).toBe('success')
      expect(toasts.value[0].duration).toBe(3000)
    })

    it('should create error toast', () => {
      const { error, toasts } = useToast()
      error('Error!')

      expect(toasts.value[0].variant).toBe('error')
      expect(toasts.value[0].duration).toBe(0)
    })

    it('should create warning toast', () => {
      const { warning, toasts } = useToast()
      warning('Warning!')

      expect(toasts.value[0].variant).toBe('warning')
      expect(toasts.value[0].duration).toBe(7000)
    })

    it('should create info toast', () => {
      const { info, toasts } = useToast()
      info('Info!')

      expect(toasts.value[0].variant).toBe('info')
      expect(toasts.value[0].duration).toBe(5000)
    })
  })

  describe('complex scenarios', () => {
    it('should handle mixed unique and duplicate toasts', () => {
      const { show, toasts } = useToast()
      show('Message A', 'success')
      show('Message B', 'info')
      show('Message A', 'success')
      show('Message C', 'warning')
      show('Message B', 'info')

      expect(toasts.value).toHaveLength(3)
      expect(toasts.value[0].count).toBe(2)
      expect(toasts.value[1].count).toBe(2)
      expect(toasts.value[2].count).toBe(1)
    })

    it('should handle rapid duplicate arrivals', () => {
      const { show, toasts } = useToast()
      show('Rapid', 'info', 5000)
      show('Rapid', 'info', 5000)
      show('Rapid', 'info', 5000)
      show('Rapid', 'info', 5000)

      expect(toasts.value).toHaveLength(1)
      expect(toasts.value[0].count).toBe(4)

      vi.advanceTimersByTime(5000)

      expect(toasts.value).toHaveLength(0)
    })

    it('should maintain separate timers for different toasts', () => {
      const { show, toasts } = useToast()
      show('Message A', 'success', 3000)
      show('Message B', 'info', 5000)

      vi.advanceTimersByTime(3000)

      expect(toasts.value).toHaveLength(1)
      expect(toasts.value[0].message).toBe('Message B')

      vi.advanceTimersByTime(2000)

      expect(toasts.value).toHaveLength(0)
    })
  })
})
