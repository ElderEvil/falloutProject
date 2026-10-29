import axios from '@/core/plugins/axios'
import type { WorldSnapshotRead } from '../models/map'

export async function getWorldPreview(seed: string): Promise<WorldSnapshotRead> {
  const response = await axios.get('/api/v1/map/dev/world', {
    params: { seed },
    _skipErrorNotification: true,
  })
  return response.data
}
