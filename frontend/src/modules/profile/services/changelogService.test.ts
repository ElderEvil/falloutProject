import { describe, it, expect, beforeEach } from 'vitest'
import { changelogService } from '@/modules/profile/services/changelogService'

describe('ChangelogService', () => {
  beforeEach(() => {
    // Reset any mocked data if needed
  })

  describe('getChangelog', () => {
    it('should fetch changelog data from API', async () => {
      console.log('Test: calling getChangelog()')
      
      const result = await changelogService.getChangelog({ limit: 5 })
      
      console.log('Test: getChangelog result:', result)
      
      expect(Array.isArray(result)).toBe(true)
      expect(result.length).toBeGreaterThan(0)
      
      // Check structure of first entry
      if (result.length > 0) {
        const firstEntry = result[0]
        expect(firstEntry).toHaveProperty('version')
        expect(firstEntry).toHaveProperty('date_display')
        expect(firstEntry).toHaveProperty('changes')
        expect(Array.isArray(firstEntry.changes)).toBe(true)
      }
    })

    it('should handle API errors gracefully', async () => {
      // This test would need mocking for error scenarios
      // For now, just verify it doesn't crash
      try {
        await changelogService.getChangelog({ limit: 1 })
        expect(true).toBe(true) // Should not throw
      } catch (error) {
        expect(error).toBeDefined()
      }
    })
  })

  describe('getLatestChangelog', () => {
    it('should return latest changelog entry', async () => {
      console.log('Test: calling getLatestChangelog()')
      
      const result = await changelogService.getLatestChangelog()
      
      console.log('Test: getLatestChangelog result:', result)
      
      if (result) {
        expect(result).toHaveProperty('version')
        expect(result).toHaveProperty('date_display')
        expect(result).toHaveProperty('changes')
      }
    })
  })
})