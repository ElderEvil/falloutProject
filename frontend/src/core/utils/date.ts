const TIMEZONE_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/i

/** Parse API timestamps that are stored as naive UTC by the backend. */
export function parseUtcDate(timestamp: string): Date {
  const normalized = timestamp.includes('T') ? timestamp : timestamp.replace(' ', 'T')
  return new Date(normalized.includes('T') && !TIMEZONE_SUFFIX.test(normalized) ? `${normalized}Z` : normalized)
}
