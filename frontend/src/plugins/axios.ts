// Re-export from core for backward compatibility
export { default } from '@/core/plugins/axios'
import apiClient from '@/core/plugins/axios'
export const api = apiClient
