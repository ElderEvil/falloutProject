<script setup lang="ts">
/**
 * ChangelogModal - Displays version updates and changelog information
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { UCard, UButton, UBadge } from '@/core/components/ui'
import { Icon } from '@iconify/vue'
import {
  changelogService,
  type ChangelogEntry,
  type ChangeEntry
} from '@/modules/profile/services/changelogService'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'

interface Props {
  show: boolean
  currentVersion?: string
  lastSeenVersion?: string
}

interface Emits {
  close: []
  markAsSeen: [version: string]
}

const props = withDefaults(defineProps<Props>(), {
  currentVersion: '2.7.5',
  lastSeenVersion: undefined
})

const emit = defineEmits<Emits>()

const changelog = ref<ChangelogEntry[]>([])
const loading = ref(false)
const error = ref('')

// Compute entries to show (either all or just new versions)
const entriesToShow = computed(() => {
  if (!props.lastSeenVersion) {
    return changelog.value.slice(0, 1)
  }

  return changelog.value.filter((entry) => {
    const lastSeen = props.lastSeenVersion!
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
  if (props.currentVersion) {
    emit('markAsSeen', props.currentVersion)
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
    console.error('Changelog fetch error:', err)
  } finally {
    loading.value = false
  }
}

const handleViewAllChangelog = () => {
  window.open(
    'https://github.com/ElderEvil/falloutProject/blob/master/CHANGELOG.md',
    '_blank'
  )
}

const handleBackdropClick = () => {
  emit('close')
}

const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.show) {
    emit('close')
  }
}

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

// Category colors and icons
const getCategoryInfo = (category: string) => {
  const categoryMap: Record<string, { color: string; icon: string }> = {
    Added: { color: 'text-[--color-terminal-green-400]', icon: 'mdi:plus-circle' },
    Fixed: { color: 'text-red-400', icon: 'mdi:wrench' },
    Changed: { color: 'text-yellow-400', icon: 'mdi:swap-horizontal' },
    Removed: { color: 'text-red-400', icon: 'mdi:minus-circle' },
    Documentation: { color: 'text-blue-400', icon: 'mdi:file-document' },
    Testing: { color: 'text-purple-400', icon: 'mdi:test-tube' }
  }
  return categoryMap[category] || { color: 'text-gray-400', icon: 'mdi:circle' }
}



// Fetch changelog when modal opens (with immediate:true for initial show=true)
watch(
  () => props.show,
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
        @click="handleBackdropClick"
      >
        <UCard
          glow
          crt
          class="w-full max-w-4xl max-h-[85vh] overflow-hidden"
          @click.stop
        >
          <template #header>
            <div class="flex items-center justify-between w-full">
              <div class="flex items-center gap-3">
                <Icon icon="mdi:history" class="h-7 w-7 text-[--color-terminal-green-400]" />
                <h2 class="text-2xl font-bold text-[--color-terminal-green-400]">What's New</h2>
              </div>
              <button
                @click="$emit('close')"
                class="text-gray-400 hover:text-[--color-terminal-green-400] transition-colors p-1"
                aria-label="Close modal"
              >
                <Icon icon="mdi:close" class="h-6 w-6" />
              </button>
            </div>
          </template>

          <!-- Loading state -->
          <div v-if="loading" class="flex items-center justify-center py-12">
            <div class="terminal-glow text-[--color-terminal-green-400]">Loading changelog...</div>
          </div>

          <!-- Error state -->
          <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
            <div class="text-red-400 mb-4">{{ error }}</div>
            <UButton variant="primary" @click="fetchChangelog">Retry</UButton>
          </div>

          <!-- No new versions -->
          <div
            v-else-if="!hasNewVersions"
            class="flex flex-col items-center justify-center py-12"
          >
            <Icon
              icon="mdi:check-circle"
              class="h-16 w-16 text-[--color-terminal-green-400] mb-4"
            />
            <div class="text-[--color-terminal-green-400] text-xl mb-2">All caught up!</div>
            <div class="text-gray-400">You're running the latest version</div>
          </div>

          <!-- Changelog content -->
          <div
            v-if="!loading && !error && changelog.length > 0"
            class="overflow-y-auto max-h-[50vh] pr-2 space-y-6"
          >
            <div v-for="entry in entriesToShow" :key="entry.version" class="mb-8 last:mb-0">
              <!-- Version header -->
              <div
                class="flex items-center justify-between mb-4 pb-2 border-b border-[--color-terminal-green-500]/30"
              >
                <div class="flex items-center gap-3">
                  <UBadge variant="success" class="text-lg"> v{{ entry.version }} </UBadge>
                  <span class="text-gray-400 text-sm font-mono">{{ entry.date_display }}</span>
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
                    <Icon :icon="getCategoryInfo(category).icon" :class="getCategoryInfo(category).color" class="h-5 w-5" />
                    <h3 :class="getCategoryInfo(category).color" class="font-semibold font-mono">
                      {{ category }}
                    </h3>
                  </div>

                  <!-- Change items -->
                  <ul class="space-y-2 ml-6">
                    <li
                      v-for="(change, idx) in changes"
                      :key="`${entry.version}-${idx}`"
                      class="text-gray-300 text-sm leading-relaxed font-mono"
                    >
                      <FormattedChangeDescription :description="change.description" />
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <template #footer>
            <div class="flex justify-between items-center">
              <div class="flex gap-3">
                <UButton variant="secondary" @click="handleViewAllChangelog">
                  View Full Changelog
                </UButton>
              </div>

              <div class="flex gap-3">
                <UButton variant="secondary" @click="$emit('close')"> Close </UButton>
                <UButton v-if="hasNewVersions" variant="primary" @click="handleMarkAsSeen">
                  Got it!
                </UButton>
              </div>
            </div>
          </template>
        </UCard>
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
  scrollbar-color: var(--color-terminal-green) transparent;
}

:deep(.overflow-y-auto)::-webkit-scrollbar {
  width: 6px;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-track {
  background: transparent;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-thumb {
  background-color: var(--color-terminal-green);
  border-radius: 3px;
}

:deep(.overflow-y-auto)::-webkit-scrollbar-thumb:hover {
  background-color: var(--color-terminal-green-glow);
}

/* Terminal-style bullets */
:deep(ul li::before) {
  content: '▸';
  color: var(--color-terminal-green);
  margin-right: 8px;
  font-weight: bold;
}
</style>
