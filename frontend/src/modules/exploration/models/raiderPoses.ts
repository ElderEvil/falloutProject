export interface RaiderPoseUrls {
  image_url?: string | null
  alt_image_url?: string | null
}

/**
 * Pick a raider pose for visual variety. This is presentation-only: the pose is
 * never persisted or treated as gameplay data. A group scene can pass each
 * raider's index as `varietySeed` so neighbours alternate.
 */
export const pickRaiderPose = (raider: RaiderPoseUrls, varietySeed = 0): string | null => {
  const urls = [raider.image_url, raider.alt_image_url].filter(
    (url): url is string => typeof url === 'string' && url.length > 0
  )
  if (!urls.length) return null
  return urls[Math.abs(varietySeed) % urls.length]
}

/** Stable per-encounter seed so the same raider keeps its pose between re-renders. */
export const raiderVarietySeed = (explorationId: string, siteId: string): number => {
  const value = `${explorationId}:${siteId}`
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0
  }
  return hash
}
