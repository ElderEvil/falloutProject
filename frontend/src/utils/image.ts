/**
 * Normalizes an image URL by ensuring it has a proper protocol.
 * Preserves existing schemes (http://, https://, data:, blob:),
 * protocol-relative URLs (//), and root-relative paths (/).
 * For schemeless hostnames, uses current page protocol or defaults to https://.
 */
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
