import apiClient from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ConsoleManifest = components['schemas']['ConsoleManifest']
export type ConsoleRequest = components['schemas']['ConsoleRequest']
export type ConsoleResult = components['schemas']['ConsoleResult']

export const consoleApi = {
  async manifest(): Promise<ConsoleManifest> {
    return (await apiClient.get<ConsoleManifest>('/api/v1/system/console/manifest')).data
  },
  async execute(request: ConsoleRequest): Promise<ConsoleResult> {
    return (await apiClient.post<ConsoleResult>('/api/v1/system/console', request)).data
  },
}
