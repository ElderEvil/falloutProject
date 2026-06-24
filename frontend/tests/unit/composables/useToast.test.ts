import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useToast } from '@/core/composables/useToast'

let toastCounter = 0

vi.mock('@nuxt/ui/composables', () => ({
  useToast: () => {
    const add = vi.fn((opts) => {
      toastCounter++
      return { id: `nuxt-toast-${toastCounter}`, ...opts }
    })
    return {
      add,
      remove: vi.fn(),
      clear: vi.fn(),
      toasts: { value: [] },
      update: vi.fn(),
    }
  },
}))

describe('useToast (@nuxt/ui adapter)', () => {
  beforeEach(() => {
    toastCounter = 0
    vi.clearAllMocks()
  })

  describe('convenience methods', () => {
    it('should create success toast', () => {
      const { success } = useToast()
      const id = success('Success!')
      expect(id).toBeTruthy()
    })

    it('should create error toast', () => {
      const { error } = useToast()
      const id = error('Error!')
      expect(id).toBeTruthy()
    })

    it('should create warning toast', () => {
      const { warning } = useToast()
      const id = warning('Warning!')
      expect(id).toBeTruthy()
    })

    it('should create info toast', () => {
      const { info } = useToast()
      const id = info('Info!')
      expect(id).toBeTruthy()
    })
  })

  describe('show function', () => {
    it('should create a toast with default info variant', () => {
      const { show } = useToast()
      const id = show('Test message')
      expect(id).toBeTruthy()
    })

    it('should create a toast with specified variant', () => {
      const { show } = useToast()
      const id = show('Error occurred', 'error')
      expect(id).toBeTruthy()
    })

    it('should return unique toast id', () => {
      const { show } = useToast()
      const id1 = show('Message 1')
      const id2 = show('Message 2')
      expect(id1).not.toBe(id2)
    })
  })

  describe('remove function', () => {
    it('should remove toast by id', () => {
      const { remove, show } = useToast()
      const id = show('Test message')
      expect(() => remove(id)).not.toThrow()
    })

    it('should not throw when removing non-existent toast', () => {
      const { remove } = useToast()
      expect(() => {
        remove('non-existent-id')
      }).not.toThrow()
    })
  })

  describe('convenience methods return ids', () => {
    it('should return unique ids for each success toast', () => {
      const { success } = useToast()
      const id1 = success('Success 1')
      const id2 = success('Success 2')
      expect(id1).not.toBe(id2)
    })

    it('should return unique ids for each error toast', () => {
      const { error } = useToast()
      const id1 = error('Error 1')
      const id2 = error('Error 2')
      expect(id1).not.toBe(id2)
    })
  })
})
