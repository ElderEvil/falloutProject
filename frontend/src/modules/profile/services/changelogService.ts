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

    try {
      const result = await apiGet<ChangelogEntry[]>(url)
      return result
    } catch (error) {
      if (error instanceof Error) {
        console.error('Changelog API error:', error.message)
      } else {
        console.error('Changelog API error:', error)
      }
      return []
    }
  }

  async getLatestChangelog(): Promise<ChangelogEntry | null> {
    try {
      return await apiGet<ChangelogEntry>(`${this.baseUrl}/latest`)
    } catch (error) {
      if (error instanceof Error) {
        console.error('Failed to fetch latest changelog:', error.message)
      } else {
        console.error('Failed to fetch latest changelog:', error)
      }
      return null
    }
  }

  async getChangelogSince(version: string, limit = 5): Promise<ChangelogEntry[]> {
    return this.getChangelog({ since: version, limit })
  }
}

export const changelogService = new ChangelogService()
