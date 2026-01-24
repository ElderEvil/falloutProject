/**
 * Normalizes an image URL by ensuring it has a proper protocol.
 * If the URL already starts with http://, https://, or /, it is returned as-is.
 * Otherwise, http:// is prepended.
 */
export const normalizeImageUrl = (url: string | null | undefined): string => {
  if (!url) return ''

  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/')) {
    return url
  }

  return `http://${url}`
}
