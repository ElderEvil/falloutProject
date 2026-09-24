type Breadcrumb = { label: string; to?: string }

const SCREEN_LABELS: [RegExp, string][] = [
  [/^\/vault\/[^/]+$/, 'Overview'],
  [/^\/vault\/[^/]+\/dwellers/, 'Dwellers'],
  [/^\/vault\/[^/]+\/map/, 'Map'],
  [/^\/profile/, 'Profile'],
  [/^\/settings/, 'Settings'],
  [/^\/preferences/, 'Preferences'],
]

const screenLabel = (path: string | null | undefined): string | null => {
  if (!path) return null
  const match = SCREEN_LABELS.find(([pattern]) => pattern.test(path))
  return match ? match[1] : null
}

/**
 * Back navigation that remembers the screen the user came from instead of
 * redirecting to one fixed location (issue #620). vue-router keeps the
 * previous in-app location in history state; when there is none (deep link or
 * refresh) the given fallback path is used.
 *
 * Returns the label for the back button, an optional explicit backTo only for
 * the deep-link case (a prior history entry is followed with router.back(),
 * which keeps history semantics instead of growing the stack), and
 * breadcrumbs showing the entry context, e.g. Profile → Settings.
 */
export function useBackNavigation(currentLabel: string, fallback: () => string) {
  const previousPath = () => (window.history.state?.back as string | undefined) ?? null

  const backTo = (): string | undefined => (previousPath() ? undefined : fallback())
  const backLabel = () => {
    const label = screenLabel(previousPath() ?? fallback())
    return label ? `Back to ${label}` : 'Back'
  }
  const breadcrumbs = (): Breadcrumb[] => {
    const path = previousPath()
    if (!path) return []
    const crumb: Breadcrumb = { label: screenLabel(path) ?? 'Previous screen', to: path }
    return [crumb, { label: currentLabel }]
  }

  return { backTo, backLabel, breadcrumbs }
}
