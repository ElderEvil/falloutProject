<script setup lang="ts">
/**
 * ChangelogView - Full changelog page
 */
import { ref, onMounted, computed } from 'vue'
import { UCard, UButton, UBadge, USkeleton } from '@/components/ui'
import { changelogService, type ChangelogEntry, type ChangeEntry } from '@/modules/profile/services/changelogService'

const changelog = ref<ChangelogEntry[]>([])
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const selectedCategory = ref('all')

// All available categories for filtering
const categories = computed(() => {
  const cats = new Set<string>()
  changelog.value.forEach(entry => {
    entry.changes.forEach(change => cats.add(change.category))
  })
  return Array.from(cats).sort()
})

// Filter changelog based on search and category
const filteredChangelog = computed(() => {
  let filtered = changelog.value

  // Category filter
  if (selectedCategory.value !== 'all') {
    filtered = filtered.map(entry => ({
      ...entry,
      changes: entry.changes.filter(change => change.category === selectedCategory.value)
    })).filter(entry => entry.changes.length > 0)
  }

  // Search filter
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.map(entry => ({
      ...entry,
      changes: entry.changes.filter(change =>
        change.description.toLowerCase().includes(query)
      )
    })).filter(entry => entry.changes.length > 0)
  }

  return filtered
})

// Group changes by category
const groupChangesByCategory = (changes: ChangeEntry[]) => {
  const grouped = new Map<string, ChangeEntry[]>()

  changes.forEach(change => {
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
    'Added': { color: 'text-green-400', icon: '✨' },
    'Fixed': { color: 'text-blue-400', icon: '🔧' },
    'Changed': { color: 'text-yellow-400', icon: '🔄' },
    'Removed': { color: 'text-red-400', icon: '🗑️' },
    'Documentation': { color: 'text-purple-400', icon: '📚' },
    'Testing': { color: 'text-cyan-400', icon: '🧪' },
    'Technical': { color: 'text-gray-400', icon: '⚙️' },
    'Security': { color: 'text-orange-400', icon: '🔒' },
    'Performance': { color: 'text-pink-400', icon: '⚡' }
  }

  return categoryMap[category] || { color: 'text-gray-300', icon: '📝' }
}

const fetchChangelog = async () => {
  loading.value = true
  error.value = ''

  try {
    changelog.value = await changelogService.getChangelog({ limit: 50 })
  } catch (err) {
    error.value = 'Failed to load changelog'
    console.error('Changelog fetch error:', err)
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
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <div class="mb-8 text-center">
      <h1 class="text-4xl font-bold text-[var(--color-theme-primary)] mb-4 terminal-glow">
        📜 Changelog
      </h1>
      <p class="text-gray-400 text-lg">
        Complete version history and release notes for Fallout Shelter Game
      </p>
    </div>

    <!-- Filters -->
    <UCard class="mb-8" glow>
      <div class="flex flex-wrap gap-4 items-center">
        <!-- Search -->
        <div class="flex-1 min-w-64">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search changelog..."
            class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-green-400 placeholder-gray-500 focus:outline-none focus:border-[var(--color-theme-primary)] focus:ring-1 focus:ring-[var(--color-theme-primary)]"
          />
        </div>

        <!-- Category Filter -->
        <div class="flex items-center gap-2">
          <label class="text-gray-400">Category:</label>
          <select
            v-model="selectedCategory"
            class="px-4 py-2 bg-gray-800 border border-gray-700 rounded text-green-400 focus:outline-none focus:border-[var(--color-theme-primary)] focus:ring-1 focus:ring-[var(--color-theme-primary)]"
          >
            <option value="all">All Categories</option>
            <option v-for="category in categories" :key="category" :value="category">
              {{ getCategoryInfo(category).icon }} {{ category }}
            </option>
          </select>
        </div>

        <!-- Clear Filters -->
        <UButton
          variant="secondary"
          @click="searchQuery = ''; selectedCategory = 'all'"
          :disabled="!searchQuery && selectedCategory === 'all'"
        >
          Clear Filters
        </UButton>
      </div>
    </UCard>

    <!-- Loading state -->
    <div v-if="loading" class="space-y-8">
      <USkeleton v-for="i in 3" :key="i" class="h-32 w-full" />
    </div>

    <!-- Error state -->
    <UCard v-else-if="error" glow class="text-center py-12">
      <div class="text-red-400 text-xl mb-4">{{ error }}</div>
      <UButton variant="primary" @click="fetchChangelog">Retry</UButton>
    </UCard>

    <!-- No results -->
    <UCard v-else-if="filteredChangelog.length === 0" glow class="text-center py-12">
      <div class="text-gray-400 text-xl mb-2">No matching entries found</div>
      <div class="text-gray-500">Try adjusting your search or filter criteria</div>
    </UCard>

    <!-- Changelog content -->
    <div v-else class="space-y-8">
      <div
        v-for="entry in filteredChangelog"
        :key="entry.version"
        class="mb-8"
      >
        <!-- Version header -->
        <UCard class="mb-4" glow>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <UBadge variant="primary" class="text-xl font-bold">
                v{{ entry.version }}
              </UBadge>
              <span class="text-gray-400">{{ entry.date_display }}</span>
            </div>
            <UButton
              variant="secondary"
              size="sm"
              @click="scrollToTop()"
            >
              ↑ Top
            </UButton>
          </div>
        </UCard>

        <!-- Changes grouped by category -->
        <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="[category, changes] in groupChangesByCategory(entry.changes)"
            :key="category"
            class="bg-gray-900 rounded-lg p-4 border border-gray-800"
          >
            <!-- Category header -->
            <div class="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700">
              <span :class="getCategoryInfo(category).color" class="text-lg">
                {{ getCategoryInfo(category).icon }}
              </span>
              <h3 :class="getCategoryInfo(category).color" class="font-semibold text-lg">
                {{ category }}
              </h3>
              <UBadge variant="secondary" class="ml-auto">
                {{ changes.length }}
              </UBadge>
            </div>

            <!-- Change items -->
            <ul class="space-y-2">
              <li
                v-for="change in changes"
                :key="change.description"
                class="text-gray-300 text-sm leading-relaxed"
              >
                <span v-html="formatChangeDescription(change.description)"></span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Back to top button -->
    <div v-if="!loading && !error && filteredChangelog.length > 0" class="fixed bottom-8 right-8">
      <UButton
        variant="primary"
        size="lg"
        @click="scrollToTop()"
        class="shadow-lg shadow-[var(--color-theme-primary)]/50"
      >
        ↑ Top
      </UButton>
    </div>
  </div>
</template>

<script lang="ts">
// Helper function to format markdown-style descriptions
function formatChangeDescription(description: string): string {
  // Handle code blocks and inline code
  description = description.replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1 rounded text-green-300">$1</code>')

  // Handle bold text
  description = description.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white">$1</strong>')

  // Handle URLs (basic)
  description = description.replace(
    /(https?:\/\/[^\s]+)/g,
    '<a href="$1" target="_blank" class="text-green-400 hover:text-green-300 underline">$1</a>'
  )

  return description
}
</script>

<style scoped>
/* Terminal-style bullets */
.space-y-2 > li::before {
  content: "▸";
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
