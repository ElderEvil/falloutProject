import apiClient from '@/core/plugins/axios'

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
    const params: Record<string, number | string> = {}

    if (options?.limit !== undefined) {
      params.limit = options.limit
    }

    if (options?.since) {
      params.since = options.since
    }

    try {
      const response = await apiClient.get<ChangelogEntry[]>(this.baseUrl, { params })
      return response.data
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
      const response = await apiClient.get<ChangelogEntry>(`${this.baseUrl}/latest`)
      return response.data
    } catch (error: any) {
      if (error?.response?.status === 404) {
        // 404 is expected when no changelog exists
        return null
      }
      // Log other errors
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
