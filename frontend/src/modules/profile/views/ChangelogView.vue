<script setup lang="ts">
/**
 * ChangelogView - Full changelog page
 */
import { ref, onMounted, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Card, CardContent } from '@/core/components/ui/card'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import { Badge } from '@/core/components/ui/badge'
import { Skeleton } from '@/core/components/ui/skeleton'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useVaultStore } from '@/modules/vault/stores/vault'
import {
  changelogService,
  type ChangelogEntry,
  type ChangeEntry,
} from '@/modules/profile/services/changelogService'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'
import { getChangelogCategoryIcon } from '@/modules/profile/components/changelogCategoryIcons'

const breadcrumbs = [{ label: 'Home', to: '/' }, { label: 'Changelog' }]
const { isCollapsed } = useSidePanel()
const vaultStore = useVaultStore()
const changelog = ref<ChangelogEntry[]>([])
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const selectedCategories = ref<string[]>([])

const clearFilters = () => {
  searchQuery.value = ''
  selectedCategories.value = []
}

const toggleCategory = (category: string) => {
  const index = selectedCategories.value.indexOf(category)
  if (index >= 0) {
    selectedCategories.value.splice(index, 1)
  } else {
    selectedCategories.value.push(category)
  }
}

const isCategorySelected = (category: string) => selectedCategories.value.includes(category)

// All available categories for filtering
const categories = computed(() => {
  const cats = new Set<string>()
  changelog.value.forEach((entry) => {
    entry.changes.forEach((change) => {
      cats.add(change.category)
    })
  })
  return Array.from(cats).sort()
})

// Filter changelog based on search and category
const filteredChangelog = computed(() => {
  let filtered = changelog.value

  // Category filter
  if (selectedCategories.value.length > 0) {
    filtered = filtered
      .map((entry) => ({
        ...entry,
        changes: entry.changes.filter((change) =>
          selectedCategories.value.includes(change.category)
        ),
      }))
      .filter((entry) => entry.changes.length > 0)
  }

  // Search filter
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered
      .map((entry) => ({
        ...entry,
        changes: entry.changes.filter((change) => change.description.toLowerCase().includes(query)),
      }))
      .filter((entry) => entry.changes.length > 0)
  }

  return filtered
})

// Group changes by category
const groupChangesByCategory = (changes: ChangeEntry[]) => {
  const grouped = new Map<string, ChangeEntry[]>()

  changes.forEach((change) => {
    if (!grouped.has(change.category)) {
      grouped.set(change.category, [])
    }
    grouped.get(change.category)!.push(change)
  })

  return grouped
}

const fetchChangelog = async () => {
  loading.value = true
  error.value = ''

  try {
    changelog.value = await changelogService.getChangelog({ limit: 50 })
  } catch {
    error.value = 'Failed to load changelog'
  } finally {
    loading.value = false
  }
}

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  fetchChangelog()
})
</script>

<template>
  <div class="min-h-screen bg-terminal-background text-theme-primary [text-shadow:none]">
    <div class="flex min-h-screen">
      <SidePanel v-if="vaultStore.activeVaultId" :vault-id="vaultStore.activeVaultId" />
      <main
        class="min-w-0 flex-1 pb-8 transition-[margin-left] duration-300 ease max-md:ml-0"
        :class="vaultStore.activeVaultId ? (isCollapsed ? 'ml-16' : 'ml-60') : ''"
      >
        <div class="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
          <PageHeader
            title="Changelog"
            icon="mdi:history"
            subtitle="Version history and release notes for Fallout Shelter."
          >
            <template #back>
              <PageNavigation back-label="Back to Home" back-to="/" :breadcrumbs="breadcrumbs" />
            </template>
          </PageHeader>

          <!-- Filters -->
          <Card class="mb-8 gap-0 border-theme-primary/20 bg-surface">
            <CardContent class="flex flex-wrap items-center gap-4">
              <div class="min-w-0 flex-1 basis-64">
                <label for="changelog-search" class="sr-only">Search release notes</label>
                <Input
                  id="changelog-search"
                  v-model="searchQuery"
                  type="text"
                  placeholder="Search changelog..."
                  class="w-full border-theme-primary/20 bg-surface-sunken text-theme-primary placeholder:text-theme-primary/40"
                />
              </div>

              <!-- Category Filter -->
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-theme-primary/60">Category:</span>
                <button
                  v-for="category in categories"
                  :key="category"
                  type="button"
                  @click="toggleCategory(category)"
                  :aria-pressed="isCategorySelected(category)"
                  class="px-3 py-1 rounded border text-sm transition-colors"
                  :class="
                    isCategorySelected(category)
                      ? 'border-theme-primary text-theme-primary bg-theme-primary/10'
                      : 'border-theme-primary/20 text-theme-primary/60 hover:border-theme-primary/40 hover:text-theme-primary'
                  "
                >
                  <Icon
                    :icon="getChangelogCategoryIcon(category)"
                    class="mr-1 inline-block size-4 align-[-0.15em]"
                  />
                  {{ category }}
                </button>
              </div>

              <!-- Clear Filters -->
              <Button
                variant="secondary"
                @click="clearFilters"
                :disabled="!searchQuery && selectedCategories.length === 0"
              >
                Clear Filters
              </Button>
            </CardContent>
          </Card>

          <!-- Loading state -->
          <div v-if="loading" class="space-y-8">
            <Skeleton v-for="i in 3" :key="i" class="h-32 w-full" />
          </div>

          <!-- Error state -->
          <Card
            v-else-if="error"
            class="gap-0 border-theme-primary/20 bg-surface py-12 text-center"
          >
            <CardContent>
              <div class="mb-4 text-xl text-danger" role="alert">{{ error }}</div>
              <Button variant="default" @click="fetchChangelog">Retry</Button>
            </CardContent>
          </Card>

          <!-- No results -->
          <Card
            v-else-if="filteredChangelog.length === 0"
            class="gap-0 border-theme-primary/20 bg-surface py-12 text-center"
          >
            <CardContent>
              <div class="mb-2 text-xl text-theme-primary/70">No matching entries found</div>
              <div class="text-theme-primary/55">Try adjusting your search or filter criteria</div>
            </CardContent>
          </Card>

          <!-- Changelog content -->
          <div v-else class="space-y-8">
            <section v-for="entry in filteredChangelog" :key="entry.version">
              <!-- Version header -->
              <Card class="mb-4 gap-0 border-theme-primary/20 bg-surface">
                <CardContent class="flex flex-wrap items-center gap-3">
                  <Badge variant="default" class="text-xl font-bold"> v{{ entry.version }} </Badge>
                  <span class="text-theme-primary/60">{{ entry.date_display }}</span>
                </CardContent>
              </Card>

              <!-- Changes grouped by category -->
              <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <div
                  v-for="[category, changes] in groupChangesByCategory(entry.changes)"
                  :key="`${entry.version}-${category}`"
                  class="rounded-lg border border-theme-primary/20 bg-surface p-5"
                >
                  <!-- Category header -->
                  <div class="mb-4 flex items-center gap-2 border-b border-theme-primary/20 pb-3">
                    <Icon
                      :icon="getChangelogCategoryIcon(category)"
                      class="size-5 shrink-0 text-theme-primary/70"
                    />
                    <h3 class="text-lg font-semibold text-theme-primary">
                      {{ category }}
                    </h3>
                    <Badge variant="secondary" class="ml-auto">
                      {{ changes.length }}
                    </Badge>
                  </div>

                  <!-- Change items -->
                  <ul class="space-y-2">
                    <li
                      v-for="(change, index) in changes"
                      :key="`${entry.version}-${category}-${index}`"
                      class="text-theme-primary/75 text-sm leading-relaxed"
                    >
                      <FormattedChangeDescription :description="change.description" />
                    </li>
                  </ul>
                </div>
              </div>
            </section>
          </div>

          <!-- Back to top button -->
          <div
            v-if="!loading && !error && filteredChangelog.length > 0"
            class="fixed bottom-4 right-4 sm:bottom-8 sm:right-8"
          >
            <Button variant="default" size="lg" @click="scrollToTop()"> ↑ Top </Button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Terminal-style bullets */
.space-y-2 > li::before {
  content: '▸';
  color: var(--color-theme-primary);
  margin-right: 8px;
  font-weight: bold;
}
</style>
