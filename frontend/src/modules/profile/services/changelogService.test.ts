import { describe, it, expect, beforeEach, vi } from 'vitest'
import { changelogService, type ChangelogEntry } from '@/modules/profile/services/changelogService'
import * as api from '@/core/utils/api'

describe('ChangelogService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getChangelog', () => {
    it('should fetch changelog data from API', async () => {
      const mockData: ChangelogEntry[] = [
        {
          version: '2.8.0',
          date: '2026-01-29T00:00:00',
          date_display: '2026-01-29',
          changes: [
            { category: 'Added', description: 'New feature' },
            { category: 'Fixed', description: 'Bug fix' },
          ],
        },
      ]

      vi.spyOn(api, 'apiGet').mockResolvedValue(mockData)

      const result = await changelogService.getChangelog({ limit: 5 })

      expect(Array.isArray(result)).toBe(true)
      expect(result.length).toBe(1)
      expect(result[0]).toHaveProperty('version')
      expect(result[0]).toHaveProperty('date_display')
      expect(result[0]).toHaveProperty('changes')
      expect(Array.isArray(result[0].changes)).toBe(true)
    })

    it('should handle API errors gracefully', async () => {
      vi.spyOn(api, 'apiGet').mockRejectedValue(new Error('API error'))

      const result = await changelogService.getChangelog({ limit: 1 })

      expect(Array.isArray(result)).toBe(true)
      expect(result.length).toBe(0)
    })
  })

  describe('getLatestChangelog', () => {
    it('should return latest changelog entry', async () => {
      const mockData: ChangelogEntry = {
        version: '2.8.0',
        date: '2026-01-29T00:00:00',
        date_display: '2026-01-29',
        changes: [{ category: 'Added', description: 'New feature' }],
      }

      vi.spyOn(api, 'apiGet').mockResolvedValue(mockData)

      const result = await changelogService.getLatestChangelog()

      expect(result).not.toBeNull()
      expect(result).toHaveProperty('version')
      expect(result).toHaveProperty('date_display')
      expect(result).toHaveProperty('changes')
    })

    it('should return null on API error', async () => {
      vi.spyOn(api, 'apiGet').mockRejectedValue(new Error('API error'))

      const result = await changelogService.getLatestChangelog()

      expect(result).toBeNull()
    })

    it('should return null on 404 error without logging', async () => {
      const error404 = new Error('Not Found')
      ;(error404 as any).response = { status: 404 }

      vi.spyOn(api, 'apiGet').mockRejectedValue(error404)
      const consoleSpy = vi.spyOn(console, 'error')

      const result = await changelogService.getLatestChangelog()

      expect(result).toBeNull()
      expect(consoleSpy).not.toHaveBeenCalled()
    })
  })
})
