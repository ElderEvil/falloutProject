<script setup lang="ts">
/**
 * ChangelogModal - Displays version updates and changelog information
 */
import { ref, computed, onMounted, watch } from "vue";
import { UCard, UButton, UModal, UBadge } from "@/core/components/ui";
import {
    changelogService,
    type ChangelogEntry,
    type ChangeEntry,
} from "@/modules/profile/services/changelogService";

interface Props {
    show: boolean;
    currentVersion?: string;
    lastSeenVersion?: string;
}

interface Emits {
    close: [];
    markAsSeen: [version: string];
}

const props = withDefaults(defineProps<Props>(), {
    currentVersion: "2.7.5",
    lastSeenVersion: undefined,
});

const emit = defineEmits<Emits>();

const changelog = ref<ChangelogEntry[]>([]);
const loading = ref(false);
const error = ref("");

// Computed property for v-model binding
const modalShow = computed({
    get: () => props.show,
    set: (value: boolean) => {
        if (!value) {
            emit("close");
        }
    },
});

// Compute entries to show (either all or just new versions)
const entriesToShow = computed(() => {
    if (!props.lastSeenVersion) {
        // First time user, show only latest
        return changelog.value.slice(0, 1);
    }

    // Show versions since last seen
    return changelog.value.filter((entry) => {
        const lastSeen = props.lastSeenVersion!;
        const current = entry.version;

        // Simple version comparison
        const [lastMajor, lastMinor, lastPatch] = lastSeen
            .split(".")
            .map(Number);
        const [currMajor, currMinor, currPatch] = current
            .split(".")
            .map(Number);

        if (currMajor > lastMajor) return true;
        if (currMajor === lastMajor && currMinor > lastMinor) return true;
        if (
            currMajor === lastMajor &&
            currMinor === lastMinor &&
            currPatch > lastPatch
        )
            return true;

        return false;
    });
});

const hasNewVersions = computed(() => entriesToShow.value.length > 0);

// Debug: log computed values
watch([changelog, entriesToShow, hasNewVersions], () => {
  console.log('changelog length:', changelog.value.length)
  console.log('entriesToShow:', entriesToShow.value)
  console.log('hasNewVersions:', hasNewVersions.value)
}, { immediate: true })

const handleMarkAsSeen = () => {
    if (props.currentVersion) {
        emit("markAsSeen", props.currentVersion);
    }
    emit("close");
};

const fetchChangelog = async () => {
  loading.value = true
  error.value = ''

  try {
    console.log('Fetching changelog...')
    changelog.value = await changelogService.getChangelog({ limit: 10 })
    console.log('Fetched changelog:', changelog.value)
  } catch (err) {
    error.value = 'Failed to load changelog'
    console.error('Changelog fetch error:', err)
  } finally {
    loading.value = false
  }
}

const handleViewAllChangelog = () => {
    // Could navigate to a full changelog page
    window.open(
        "https://github.com/ElderEvil/falloutProject/blob/master/CHANGELOG.md",
        "_blank",
    );
};
</script>

<template>
    <UModal v-model="modalShow" @close="$emit('close')" size="lg">
        <UCard
            title="📜 What's New"
            glow
            crt
            class="w-full max-w-4xl max-h-[80vh] overflow-hidden"
        >
            <!-- Loading state -->
            <div v-if="loading" class="flex items-center justify-center py-12">
                <div class="terminal-glow text-green-400">
                    Loading changelog...
                </div>
            </div>

            <!-- Error state -->
            <div
                v-else-if="error"
                class="flex flex-col items-center justify-center py-12"
            >
                <div class="text-red-400 mb-4">{{ error }}</div>
                <UButton variant="primary" @click="fetchChangelog"
                    >Retry</UButton
                >
            </div>

            <!-- No new versions -->
            <div
                v-else-if="!hasNewVersions"
                class="flex flex-col items-center justify-center py-12"
            >
                <div class="text-green-400 text-xl mb-2">✅ All caught up!</div>
                <div class="text-gray-400">
                    You're running the latest version
                </div>
            </div>

            <!-- Changelog content -->
            <div
                v-if="!loading && !error && changelog.length > 0"
                class="overflow-y-auto max-h-[60vh] pr-2"
            >
                <div
                    v-for="entry in entriesToShow"
                    :key="entry.version"
                    class="mb-8 last:mb-0"
                >
                    <!-- Version header -->
                    <div
                        class="flex items-center justify-between mb-4 pb-2 border-b border-green-500/30"
                    >
                        <div class="flex items-center gap-3">
                            <UBadge variant="primary" class="text-lg">
                                v{{ entry.version }}
                            </UBadge>
                            <span class="text-gray-400 text-sm">{{
                                entry.date_display
                            }}</span>
                        </div>
                    </div>

                    <!-- Changes grouped by category -->
                    <div class="space-y-4">
                        <div
                            v-for="[
                                category,
                                changes,
                            ] in groupChangesByCategory(entry.changes)"
                            :key="category"
                            class="mb-4"
                        >
                            <!-- Category header -->
                            <div class="flex items-center gap-2 mb-3">
                                <span :class="getCategoryInfo(category).color">
                                    {{ getCategoryInfo(category).icon }}
                                </span>
                                <h3
                                    :class="getCategoryInfo(category).color"
                                    class="font-semibold"
                                >
                                    {{ category }}
                                </h3>
                            </div>

                            <!-- Change items -->
                            <ul class="space-y-2 ml-6">
                                <li
                                    v-for="change in changes"
                                    :key="change.description"
                                    class="text-gray-300 text-sm leading-relaxed"
                                >
                                    <!-- Parse markdown-style links and formatting -->
                                    <span
                                        v-html="
                                            formatChangeDescription(
                                                change.description,
                                            )
                                        "
                                    ></span>
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
                        <UButton
                            variant="secondary"
                            @click="handleViewAllChangelog"
                        >
                            View Full Changelog
                        </UButton>
                    </div>

                    <div class="flex gap-3">
                        <UButton variant="secondary" @click="$emit('close')">
                            Close
                        </UButton>
                        <UButton
                            v-if="hasNewVersions"
                            variant="primary"
                            @click="handleMarkAsSeen"
                        >
                            Got it!
                        </UButton>
                    </div>
                </div>
            </template>
        </UCard>
    </UModal>
</template>

<script lang="ts">
// Helper function to format markdown-style descriptions
function formatChangeDescription(description: string): string {
    // Handle code blocks and inline code
    description = description.replace(
        /`([^`]+)`/g,
        '<code class="bg-gray-800 px-1 rounded text-green-300">$1</code>',
    );

    // Handle bold text
    description = description.replace(
        /\*\*([^*]+)\*\*/g,
        '<strong class="text-white">$1</strong>',
    );

    // Handle URLs (basic)
    description = description.replace(
        /(https?:\/\/[^\s]+)/g,
        '<a href="$1" target="_blank" class="text-green-400 hover:text-green-300 underline">$1</a>',
    );

    return description;
}
</script>

<style scoped>
/* Target UCard header within modal context */
:deep(.card-header) {
    background: linear-gradient(
        90deg,
        var(--color-theme-primary) 0%,
        transparent 100%
    );
    border-bottom: 2px solid var(--color-theme-primary);
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
:deep(.space-y-2 > li::before) {
    content: "▸";
    color: var(--color-theme-primary);
    margin-right: 8px;
    font-weight: bold;
}
</style>
