/**
 * Normalizes an image URL by ensuring it has a proper protocol.
 * Preserves existing schemes (http://, https://, data:, blob:),
 * protocol-relative URLs (//), and root-relative paths (/).
 * For schemeless hostnames, uses current page protocol or defaults to https://.
 */
import { API_BASE_URL } from '@/core/config/api'

export const normalizeImageUrl = (url: string | null | undefined): string => {
  if (!url) return ''

  // Preserve data: and blob: URLs
  if (url.startsWith('data:') || url.startsWith('blob:')) {
    return url
  }

  // Preserve URLs with explicit schemes (http://, https://, etc.)
  if (url.includes('://')) {
    return url
  }

  // Preserve protocol-relative URLs
  if (url.startsWith('//')) {
    return url
  }

  // Preserve root-relative and relative paths
  if (url.startsWith('/')) {
    return url
  }

  // Schemeless hostname - use current page protocol or default to https://
  const protocol = typeof window !== 'undefined' ? window.location.protocol : 'https:'
  return `${protocol}//${url}`
}

/**
 * Builds a full URL for a room image by prepending API_BASE_URL.
 * Handles trailing slash on the base and leading slash on the path.
 */
export function getRoomImageUrl(imageUrl: string | null | undefined): string | null {
  if (!imageUrl) return null
  const normalizedBase = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL
  const imagePath = imageUrl.startsWith('/') ? imageUrl.slice(1) : imageUrl
  return `${normalizedBase}/${imagePath}`
}
