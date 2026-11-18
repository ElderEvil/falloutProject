import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'

export type ConsoleManifest = components['schemas']['ConsoleManifest']
export type ConsoleRequest = components['schemas']['ConsoleRequest']
export type ConsoleResult = components['schemas']['ConsoleResult']

export const consoleApi = {
  async manifest(): Promise<ConsoleManifest> {
    return apiGet<ConsoleManifest>('/api/v1/system/console/manifest')
  },
  async execute(request: ConsoleRequest): Promise<ConsoleResult> {
    return apiPost<ConsoleResult>('/api/v1/system/console', request)
  },
}
