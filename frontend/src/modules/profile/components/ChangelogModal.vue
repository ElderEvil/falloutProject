<script setup lang="ts">
/**
 * ChangelogModal - Displays version updates and changelog information
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Icon } from '@iconify/vue'
import {
  changelogService,
  type ChangelogEntry,
  type ChangeEntry,
} from '@/modules/profile/services/changelogService'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'
import { getChangelogCategoryIcon } from '@/modules/profile/components/changelogCategoryIcons'
import { useToast } from '@/core/composables/useToast'

interface Props {
  show: boolean
  currentVersion?: string
  lastSeenVersion?: string
}

interface Emits {
  close: []
  markAsSeen: [version: string]
}

const { currentVersion = '2.7.5', lastSeenVersion = undefined, show } = defineProps<Props>()

const emit = defineEmits<Emits>()

const changelog = ref<ChangelogEntry[]>([])
const loading = ref(false)
const error = ref('')
const toast = useToast()

// Compute entries to show (either all or just new versions)
const entriesToShow = computed(() => {
  if (!lastSeenVersion) {
    return changelog.value.slice(0, 1)
  }

  return changelog.value.filter((entry) => {
    const lastSeen = lastSeenVersion!
    const current = entry.version

    const [lastMajor, lastMinor, lastPatch] = lastSeen.split('.').map(Number)
    const [currMajor, currMinor, currPatch] = current.split('.').map(Number)

    if (currMajor > lastMajor) return true
    if (currMajor === lastMajor && currMinor > lastMinor) return true
    if (currMajor === lastMajor && currMinor === lastMinor && currPatch > lastPatch) return true

    return false
  })
})

const hasNewVersions = computed(() => entriesToShow.value.length > 0)

const handleMarkAsSeen = () => {
  if (currentVersion) {
    emit('markAsSeen', currentVersion)
  }
  emit('close')
}

const fetchChangelog = async () => {
  loading.value = true
  error.value = ''

  try {
    changelog.value = await changelogService.getChangelog({ limit: 10 })
  } catch (err) {
    error.value = 'Failed to load changelog'
    toast.error('Failed to load changelog')
  } finally {
    loading.value = false
  }
}

const handleViewAllChangelog = () => {
  window.open('https://github.com/ElderEvil/falloutProject/blob/master/CHANGELOG.md', '_blank')
}

const handleEscape = (event: KeyboardEvent) => event.key === 'Escape' && show && emit('close')

// Group changes by category
const groupChangesByCategory = (changes: ChangeEntry[]) => {
  const grouped = new Map<string, ChangeEntry[]>()

  changes.forEach((change) => {
    if (!grouped.has(change.category)) {
      grouped.set(change.category, [])
    }
    grouped.get(change.category)!.push(change)
  })

  return Array.from(grouped.entries())
}

// Fetch changelog when modal opens (with immediate:true for initial show=true)
watch(
  () => show,
  (newShow) => {
    if (newShow) {
      fetchChangelog()
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  },
  { immediate: true }
)

// Cleanup on unmount: remove keydown listener and reset overflow
onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[9999] p-4"
        @click="$emit('close')"
      >
        <!-- @vue-ignore -->
        <Card
          class="w-full max-w-4xl max-h-[85vh] overflow-hidden gap-0 border-theme-primary/20 bg-surface p-6 [text-shadow:none]"
          @click.stop
        >
          <div class="mb-4 border-b border-theme-primary/20 pb-4">
            <div class="flex items-center justify-between w-full">
              <div class="flex items-center gap-3">
                <Icon icon="mdi:history" class="h-7 w-7 text-theme-primary" />
                <h2 class="text-2xl font-bold text-theme-primary">What's new</h2>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                class="text-theme-primary/60 hover:text-theme-primary transition-colors"
                aria-label="Close modal"
                @click="$emit('close')"
              >
                <Icon icon="mdi:close" class="h-6 w-6" />
              </Button>
            </div>
          </div>

          <!-- Loading state -->
          <div v-if="loading" class="flex items-center justify-center py-12">
            <div class="text-theme-primary">Loading changelog...</div>
          </div>

          <!-- Error state -->
          <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
            <div class="text-red-400 mb-4">{{ error }}</div>
            <Button variant="default" @click="fetchChangelog">Retry</Button>
          </div>

          <!-- No new versions -->
          <div v-else-if="!hasNewVersions" class="flex flex-col items-center justify-center py-12">
            <Icon
              icon="mdi:check-circle"
              class="h-16 w-16 text-theme-primary mb-4"
            />
            <div class="text-theme-primary text-xl mb-2">All caught up!</div>
            <div class="text-theme-primary/60">You're running the latest version</div>
          </div>

          <!-- Changelog content -->
          <div
            v-if="!loading && !error && changelog.length > 0"
            class="overflow-y-auto max-h-[50vh] pr-2 space-y-6"
          >
            <div v-for="entry in entriesToShow" :key="entry.version" class="mb-8 last:mb-0">
              <!-- Version header -->
              <div
                class="flex items-center justify-between mb-4 pb-2 border-b border-theme-primary/20"
              >
                <div class="flex items-center gap-3">
                  <Badge variant="default" class="text-lg"> v{{ entry.version }} </Badge>
                  <span class="text-theme-primary/60 text-sm font-mono">{{ entry.date_display }}</span>
                </div>
              </div>

              <!-- Changes grouped by category -->
              <div class="space-y-4">
                <div
                  v-for="[category, changes] in groupChangesByCategory(entry.changes)"
                  :key="`${entry.version}-${category}`"
                  class="mb-4"
                >
                  <!-- Category header -->
                  <div class="flex items-center gap-2 mb-3">
                    <Icon
                      :icon="getChangelogCategoryIcon(category)"
                      class="h-5 w-5 text-theme-primary/70"
                    />
                    <h3 class="font-semibold font-mono text-theme-primary">
                      {{ category }}
                    </h3>
                  </div>

                  <!-- Change items -->
                  <ul class="space-y-2 ml-6">
                    <li
                      v-for="(change, idx) in changes"
                      :key="`${entry.version}-${idx}`"
                      class="text-theme-primary/75 text-sm leading-relaxed font-mono"
                    >
                      <FormattedChangeDescription :description="change.description" />
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-4 border-t border-theme-primary/20 pt-4">
            <div class="flex justify-between items-center">
              <div class="flex gap-3">
                <Button variant="outline" @click="handleViewAllChangelog">
                  View Full Changelog
                </Button>
              </div>

              <div class="flex gap-3">
                <Button v-if="hasNewVersions" variant="default" @click="handleMarkAsSeen">
                  Got it!
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* Custom scrollbar for changelog content */
:deep(.overflow-y-auto) {
  scrollbar-width: thin;
  scrollbar-color: var(--color-theme-primary) transparent;
}

:deep(.overflow-y-auto)::-webkit-scrollbar {
  width: 6px;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-track {
  background: transparent;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-thumb {
  background-color: var(--color-theme-primary);
  border-radius: 3px;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-thumb:hover {
  background-color: var(--color-theme-glow);
}

/* Terminal-style bullets */
:deep(ul li::before) {
  content: '▸';
  color: var(--color-theme-primary);
  margin-right: 8px;
  font-weight: bold;
}
</style>
