const categoryIcons: Record<string, string> = {
  Added: 'mdi:plus-circle-outline',
  Fixed: 'mdi:wrench-outline',
  Changed: 'mdi:swap-horizontal',
  Removed: 'mdi:minus-circle-outline',
  Documentation: 'mdi:file-document-outline',
  Testing: 'mdi:test-tube',
  Technical: 'mdi:cog-outline',
  Security: 'mdi:shield-check-outline',
  Performance: 'mdi:speedometer',
}

export const getChangelogCategoryIcon = (category: string): string =>
  categoryIcons[category] ?? 'mdi:text-box-outline'
