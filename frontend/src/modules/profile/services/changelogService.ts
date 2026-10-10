import { apiGet } from '@/core/utils/api'
import { useToast } from '@/core/composables/useToast'

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
      return await apiGet<ChangelogEntry[]>(this.baseUrl, { params })
    } catch {
      useToast().error('Failed to load changelog')
      return []
    }
  }

  async getLatestChangelog(): Promise<ChangelogEntry | null> {
    try {
      return await apiGet<ChangelogEntry>(`${this.baseUrl}/latest`)
    } catch (error) {
      if (error && typeof error === 'object' && (error as { status?: number }).status === 404) {
        return null
      }
      useToast().error('Failed to load the latest changelog')
      return null
    }
  }

  async getChangelogSince(version: string, limit = 5): Promise<ChangelogEntry[]> {
    return this.getChangelog({ since: version, limit })
  }
}

export const changelogService = new ChangelogService()
