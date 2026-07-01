import { apiGet, ApiError } from '@/core/plugins/httpClient'

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

  async getChangelog(options?: { limit?: number; since?: string }): Promise<ChangelogEntry[]> {
    const params = new URLSearchParams()
    if (options?.limit !== undefined) {
      params.set('limit', String(options.limit))
    }
    if (options?.since) {
      params.set('since', options.since)
    }
    const queryString = params.toString()
    const url = queryString ? `${this.baseUrl}?${queryString}` : this.baseUrl

    try {
      return await apiGet<ChangelogEntry[]>(url)
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        console.error('Changelog API error:', error.message)
      } else if (error instanceof Error) {
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
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 404) {
        // 404 is expected when no changelog exists
        return null
      }
      if (error instanceof ApiError) {
        console.error('Failed to fetch latest changelog:', error.message)
      } else if (error instanceof Error) {
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
