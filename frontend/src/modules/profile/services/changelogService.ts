import { apiGet } from '@/core/utils/api'

export interface ChangelogEntry {
  version: string
  date: string
  date_display: string
  changes: ChangeEntry[]
}

export interface ChangeEntry {
  category: string
  description: string
}

class ChangelogService {
  private readonly baseUrl = '/api/v1/system/changelog'

  async getChangelog(options?: {
    limit?: number
    since?: string
  }): Promise<ChangelogEntry[]> {
    const params = new URLSearchParams()

    if (options?.limit) {
      params.append('limit', options.limit.toString())
    }

    if (options?.since) {
      params.append('since', options.since)
    }

    const url = `${this.baseUrl}?${params.toString()}`
    console.log('Fetching changelog from:', url)

    try {
      console.log('Making axios GET request...')
      const result = await apiGet(url)
      console.log('Changelog API result:', result)
      return result
    } catch (error) {
      console.error('Changelog API error:', error)
      console.error('Error details:', error.message, error.status, error.response?.data)
      console.error('Full error object:', error)

      // Fallback to empty array to prevent UI from breaking
      return []
    }
  }

  async getLatestChangelog(): Promise<ChangelogEntry | null> {
    try {
      return await apiGet(`${this.baseUrl}/latest`)
    } catch (error) {
      console.error('Failed to fetch latest changelog:', error)
      return null
    }
  }

  async getChangelogSince(version: string, limit = 5): Promise<ChangelogEntry[]> {
    return this.getChangelog({ since: version, limit })
  }
}

export const changelogService = new ChangelogService()
