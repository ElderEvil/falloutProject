<script setup lang="ts">
/**
 * ChangelogView - Full changelog page
 */
import { ref, onMounted, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import { Badge } from '@/core/components/ui/badge'
import { Skeleton } from '@/core/components/ui/skeleton'
import {
  changelogService,
  type ChangelogEntry,
  type ChangeEntry,
} from '@/modules/profile/services/changelogService'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'

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

// Category colors and icons
const getCategoryInfo = (category: string) => {
  const categoryMap: Record<string, { color: string; icon: string }> = {
    Added: { color: 'text-green-400', icon: '✨' },
    Fixed: { color: 'text-blue-400', icon: '🔧' },
    Changed: { color: 'text-yellow-400', icon: '🔄' },
    Removed: { color: 'text-red-400', icon: '🗑️' },
    Documentation: { color: 'text-purple-400', icon: '📚' },
    Testing: { color: 'text-cyan-400', icon: '🧪' },
    Technical: { color: 'text-theme-primary/60', icon: '⚙️' },
    Security: { color: 'text-orange-400', icon: '🔒' },
    Performance: { color: 'text-pink-400', icon: '⚡' },
  }

  return categoryMap[category] || { color: 'text-theme-primary/75', icon: '📝' }
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
  <div class="container mx-auto px-4 py-8 [text-shadow:none]">
    <!-- Header -->
    <div class="mb-8 text-center">
      <h1
        class="text-4xl font-bold text-theme-primary mb-4 flex items-center justify-center gap-3"
      >
        <Icon icon="mdi:console-line" class="w-10 h-10" />
        Changelog
      </h1>
      <p class="text-theme-primary/60 text-lg">
        Complete version history and release notes for Fallout Shelter Game
      </p>
    </div>

    <!-- Filters -->
    <Card class="mb-8 gap-0 border-theme-primary/20 bg-surface">
      <div class="flex flex-wrap gap-4 items-center">
        <div class="flex-1 min-w-64">
          <Input
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
            {{ getCategoryInfo(category).icon }} {{ category }}
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
      </div>
    </Card>

    <!-- Loading state -->
    <div v-if="loading" class="space-y-8">
      <Skeleton v-for="i in 3" :key="i" class="h-32 w-full" />
    </div>

    <!-- Error state -->
    <Card v-else-if="error" class="gap-0 border-theme-primary/20 bg-surface py-12 text-center">
      <div class="text-red-400 text-xl mb-4">{{ error }}</div>
      <Button variant="default" @click="fetchChangelog">Retry</Button>
    </Card>

    <!-- No results -->
    <Card v-else-if="filteredChangelog.length === 0" class="gap-0 border-theme-primary/20 bg-surface py-12 text-center">
      <div class="text-theme-primary/60 text-xl mb-2">No matching entries found</div>
      <div class="text-theme-primary/50">Try adjusting your search or filter criteria</div>
    </Card>

    <!-- Changelog content -->
    <div v-else class="space-y-8">
      <div v-for="entry in filteredChangelog" :key="entry.version" class="mb-8">
        <!-- Version header -->
        <Card class="mb-4 gap-0 border-theme-primary/20 bg-surface">
          <div class="flex items-center gap-3">
            <Badge variant="default" class="text-xl font-bold"> v{{ entry.version }} </Badge>
            <span class="text-theme-primary/60">{{ entry.date_display }}</span>
          </div>
        </Card>

        <!-- Changes grouped by category -->
        <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="[category, changes] in groupChangesByCategory(entry.changes)"
            :key="`${entry.version}-${category}`"
            class="bg-surface rounded-lg p-4 border border-theme-primary/20"
          >
            <!-- Category header -->
            <div class="flex items-center gap-2 mb-3 pb-2 border-b border-theme-primary/20">
              <span :class="getCategoryInfo(category).color" class="text-lg">
                {{ getCategoryInfo(category).icon }}
              </span>
              <h3 :class="getCategoryInfo(category).color" class="font-semibold text-lg">
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
      </div>
    </div>

    <!-- Back to top button -->
    <div v-if="!loading && !error && filteredChangelog.length > 0" class="fixed bottom-8 right-8">
      <Button
        variant="default"
        size="lg"
        @click="scrollToTop()"
      >
        ↑ Top
      </Button>
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

/* Custom scrollbar */
.overflow-y-auto {
  scrollbar-width: thin;
  scrollbar-color: var(--color-theme-primary) transparent;
}

.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background-color: var(--color-theme-primary);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background-color: var(--color-theme-glow);
}
</style>
