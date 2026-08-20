import axios from '@/core/plugins/axios'
import type { Relationship } from '../models/relationship'

/**
 * Relationship API calls. Store state and side effects stay in the store;
 * HTTP requests live here (Store → Service → API).
 */
export const relationshipService = {
  async marry(relationshipId: string): Promise<Relationship> {
    const response = await axios.put<Relationship>(
      `/api/v1/relationships/${relationshipId}/marry`
    )
    return response.data
  },
}
