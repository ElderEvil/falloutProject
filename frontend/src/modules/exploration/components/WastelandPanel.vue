<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "@/modules/auth/stores/auth";
import { useDwellerStore } from "@/stores/dweller";
import { useExplorationStore } from "@/stores/exploration";
import { useVaultStore } from "@/modules/vault/stores/vault";
import { Icon } from "@iconify/vue";
import ExplorationRewardsModal from "@/modules/exploration/components/ExplorationRewardsModal.vue";
import type { RewardsSummary } from "@/stores/exploration";

const route = useRoute();
const authStore = useAuthStore();
const dwellerStore = useDwellerStore();
const explorationStore = useExplorationStore();
const vaultStore = useVaultStore();

const vaultId = computed(() => route.params.id as string);

const isDraggingOver = ref(false);
const sendError = ref<string | null>(null);
const sendSuccess = ref<string | null>(null);
const showDurationModal = ref(false);
const pendingDweller = ref<{
    dwellerId: string;
    firstName: string;
    lastName: string;
    currentRoomId?: string;
} | null>(null);
const selectedDuration = ref(4);
const selectedStimpaks = ref(0);
const selectedRadaways = ref(0);

// Rewards modal state
const showRewardsModal = ref(false);
const completedExplorationRewards = ref<RewardsSummary | null>(null);
const completedDwellerName = ref("");

// Track explorations being completed to prevent duplicate calls
const completingExplorations = ref<Set<string>>(new Set());

// Fetch active explorations on mount
onMounted(async () => {
    if (vaultId.value && authStore.token) {
        try {
            await explorationStore.fetchExplorationsByVault(
                vaultId.value,
                authStore.token,
            );
        } catch (error) {
            console.error("Failed to load explorations:", error);
        }
    }
});

// Poll for exploration updates every 30 seconds and check for completion
let pollInterval: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
    pollInterval = setInterval(async () => {
        if (
            vaultId.value &&
            authStore.token &&
            explorationStore.activeExplorations
        ) {
            try {
                await explorationStore.fetchExplorationsByVault(
                    vaultId.value,
                    authStore.token,
                );

                // Check for completed explorations
                for (const exploration of activeExplorationsArray.value) {
                    const progress = getProgressPercentage(exploration.id);
                    if (
                        progress >= 100 &&
                        exploration.status === "active" &&
                        !completingExplorations.value.has(exploration.id)
                    ) {
                        // Auto-complete exploration
                        await handleCompleteExploration(exploration.id);
                    }
                }
            } catch (error) {
                console.error("Failed to poll explorations:", error);
            }
        }
    }, 30000);
});

onUnmounted(() => {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
});

const activeExplorationsArray = computed(() => {
    return Object.values(explorationStore.activeExplorations);
});

const getDwellerById = (dwellerId: string) => {
    return dwellerStore.dwellers.find((d) => d.id === dwellerId);
};

const handleDragOver = (event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer!.dropEffect = "move";
    isDraggingOver.value = true;
};

const handleDragLeave = () => {
    isDraggingOver.value = false;
};

const handleDrop = async (event: DragEvent) => {
    event.preventDefault();
    isDraggingOver.value = false;
    sendError.value = null;
    sendSuccess.value = null;

    try {
        const data = JSON.parse(
            event.dataTransfer!.getData("application/json"),
        );
        const { dwellerId, firstName, lastName, currentRoomId } = data;

        // Store dweller info and show duration modal
        pendingDweller.value = {
            dwellerId,
            firstName,
            lastName,
            currentRoomId,
        };

        // Reset medical supplies based on what the dweller already has
        const dweller = getDwellerById(dwellerId);
        if (dweller) {
            selectedStimpaks.value = Math.min(dweller.stimpack || 0, 25); // Clamp to backend limit of 25
            selectedRadaways.value = Math.min(dweller.radaway || 0, 25); // Clamp to backend limit of 25
        } else {
            selectedStimpaks.value = 0;
            selectedRadaways.value = 0;
        }

        showDurationModal.value = true;
    } catch (error) {
        console.error("Failed to parse dweller data:", error);
        sendError.value = "Failed to send dweller to wasteland";
        setTimeout(() => {
            sendError.value = null;
        }, 3000);
    }
};

const confirmSendToWasteland = async () => {
    if (!pendingDweller.value || !vaultId.value) return;

    try {
        const { dwellerId, firstName, lastName, currentRoomId } =
            pendingDweller.value;

        // If dweller is assigned to a room, unassign them first
        if (currentRoomId) {
            await dwellerStore.unassignDwellerFromRoom(
                dwellerId,
                authStore.token as string,
            );
        }

        // Send to wasteland
        await explorationStore.sendDwellerToWasteland(
            vaultId.value,
            dwellerId,
            selectedDuration.value,
            authStore.token as string,
            selectedStimpaks.value,
            selectedRadaways.value,
        );

        sendSuccess.value = `${firstName} ${lastName} sent to the wasteland for ${selectedDuration.value} hour(s)!`;

        setTimeout(() => {
            sendSuccess.value = null;
        }, 4000);

        // Close modal and reset
        showDurationModal.value = false;
        pendingDweller.value = null;
        selectedDuration.value = 4;
        selectedStimpaks.value = 0;
        selectedRadaways.value = 0;
    } catch (error) {
        console.error("Failed to send dweller to wasteland:", error);
        sendError.value = "Failed to send dweller to wasteland";
        setTimeout(() => {
            sendError.value = null;
        }, 3000);
    }
};

const cancelSend = () => {
    showDurationModal.value = false;
    pendingDweller.value = null;
    selectedDuration.value = 4;
    selectedStimpaks.value = 0;
    selectedRadaways.value = 0;
};

const formatTimeRemaining = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
};

const getProgressPercentage = (explorationId: string) => {
    const exploration = explorationStore.activeExplorations[explorationId];
    if (!exploration) return 0;

    const now = Date.now();
    // Parse as UTC by appending 'Z' if not present
    let startTimeStr = exploration.start_time;
    if (!startTimeStr.endsWith("Z")) {
        startTimeStr = startTimeStr.replace(" ", "T") + "Z";
    }
    const start = new Date(startTimeStr).getTime();
    const duration = exploration.duration * 3600 * 1000; // hours to ms
    const elapsed = now - start;

    return Math.min(100, (elapsed / duration) * 100);
};

const recallDweller = async (explorationId: string) => {
    if (!authStore.token) return;

    try {
        const exploration = explorationStore.activeExplorations[explorationId];
        if (!exploration) {
            console.error("Exploration not found:", explorationId);
            return;
        }

        const dweller = getDwellerById(exploration.dweller_id);
        if (!dweller) {
            console.error("Dweller not found:", exploration.dweller_id);
            return;
        }

        const result = await explorationStore.recallDweller(
            explorationId,
            authStore.token,
        );

        // Show rewards modal
        if (result?.rewards_summary) {
            completedExplorationRewards.value = result.rewards_summary;
            completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`;
            showRewardsModal.value = true;
        }

        // Refresh vault and dweller data
        if (vaultId.value) {
            await vaultStore.refreshVault(vaultId.value, authStore.token);
            await dwellerStore.fetchDwellersByVault(
                vaultId.value,
                authStore.token,
            );
        }
    } catch (error) {
        console.error("Failed to recall dweller:", error);
        sendError.value = "Failed to recall dweller";
        setTimeout(() => {
            sendError.value = null;
        }, 3000);
    }
};

const handleCompleteExploration = async (explorationId: string) => {
    if (!authStore.token) return;

    // Prevent duplicate calls
    if (completingExplorations.value.has(explorationId)) {
        return;
    }

    completingExplorations.value.add(explorationId);

    try {
        const exploration = explorationStore.activeExplorations[explorationId];
        if (!exploration) {
            console.error("Exploration not found:", explorationId);
            completingExplorations.value.delete(explorationId);
            return;
        }

        const dweller = getDwellerById(exploration.dweller_id);
        if (!dweller) {
            console.error("Dweller not found:", exploration.dweller_id);
            completingExplorations.value.delete(explorationId);
            return;
        }

        const result = await explorationStore.completeExploration(
            explorationId,
            authStore.token,
        );

        // Show rewards modal
        if (result?.rewards_summary) {
            completedExplorationRewards.value = result.rewards_summary;
            completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`;
            showRewardsModal.value = true;
        }

        // Refresh vault and dweller data
        if (vaultId.value) {
            await vaultStore.refreshVault(vaultId.value, authStore.token);
            await dwellerStore.fetchDwellersByVault(
                vaultId.value,
                authStore.token,
            );
        }
    } catch (error) {
        console.error("Failed to complete exploration:", error);
        sendError.value = "Failed to complete exploration";
        setTimeout(() => {
            sendError.value = null;
        }, 3000);
    } finally {
        completingExplorations.value.delete(explorationId);
    }
};

const closeRewardsModal = () => {
    showRewardsModal.value = false;
    completedExplorationRewards.value = null;
    completedDwellerName.value = "";
};
</script>

<template>
    <div class="wasteland-panel">
        <!-- Success/Error notifications -->
        <div v-if="sendSuccess" class="notification notification-success">
            <Icon icon="mdi:check-circle" class="h-5 w-5" />
            {{ sendSuccess }}
        </div>
        <div v-if="sendError" class="notification notification-error">
            <Icon icon="mdi:alert-circle" class="h-5 w-5" />
            {{ sendError }}
        </div>

        <div
            class="wasteland-dropzone"
            :class="{ 'drag-over': isDraggingOver }"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop"
        >
            <div class="dropzone-content">
                <div class="dropzone-header">
                    <Icon icon="mdi:map-marker-radius" class="dropzone-icon" />
                    <div>
                        <h3 class="dropzone-title">The Wasteland</h3>
                        <p class="dropzone-subtitle">
                            Drag dwellers here to send them exploring
                        </p>
                    </div>
                </div>
                <div v-if="isDraggingOver" class="drop-indicator">
                    <Icon
                        icon="mdi:arrow-down-bold"
                        class="h-8 w-8 animate-bounce"
                    />
                    <span>Release to send!</span>
                </div>
            </div>

            <!-- Active Explorations -->
            <div
                v-if="activeExplorationsArray.length > 0"
                class="exploring-dwellers"
            >
                <div class="explorers-header">
                    <h4 class="text-sm font-bold text-wasteland">
                        <Icon
                            icon="mdi:account-search"
                            class="inline h-5 w-5"
                        />
                        Active Explorers ({{ activeExplorationsArray.length }})
                    </h4>
                    <router-link
                        :to="`/vault/${vaultId}/exploration`"
                        class="view-all-btn"
                        title="View full exploration dashboard"
                    >
                        <Icon icon="mdi:arrow-right" class="h-4 w-4" />
                        View All
                    </router-link>
                </div>
                <div class="explorer-list">
                    <div
                        v-for="exploration in activeExplorationsArray"
                        :key="exploration.id"
                        class="explorer-card"
                    >
                        <div class="explorer-info">
                            <div class="flex items-center gap-2 mb-1">
                                <Icon
                                    icon="mdi:account"
                                    class="h-5 w-5 text-wasteland"
                                />
                                <span class="font-bold text-sm"
                                    >{{
                                        getDwellerById(exploration.dweller_id)
                                            ?.first_name
                                    }}
                                    {{
                                        getDwellerById(exploration.dweller_id)
                                            ?.last_name
                                    }}</span
                                >
                            </div>
                            <div class="explorer-stats">
                                <div class="stat-item">
                                    <Icon
                                        icon="mdi:map-marker-distance"
                                        class="h-4 w-4"
                                    />
                                    <span
                                        >{{
                                            exploration.total_distance || 0
                                        }}
                                        miles</span
                                    >
                                </div>
                                <div class="stat-item">
                                    <Icon
                                        icon="mdi:treasure-chest"
                                        class="h-4 w-4"
                                    />
                                    <span
                                        >{{
                                            exploration.loot_collected
                                                ?.length || 0
                                        }}
                                        items</span
                                    >
                                </div>
                                <div class="stat-item">
                                    <Icon
                                        icon="mdi:currency-usd"
                                        class="h-4 w-4"
                                    />
                                    <span
                                        >{{
                                            exploration.total_caps_found || 0
                                        }}
                                        caps</span
                                    >
                                </div>
                            </div>
                            <!-- Progress Bar -->
                            <div class="progress-bar-container">
                                <div
                                    class="progress-bar"
                                    :style="{
                                        width: `${getProgressPercentage(exploration.id)}%`,
                                    }"
                                ></div>
                            </div>
                            <div class="text-xs text-wasteland-dim mt-1">
                                {{
                                    Math.round(
                                        getProgressPercentage(exploration.id),
                                    )
                                }}% complete
                            </div>
                        </div>
                        <div class="explorer-actions">
                            <button
                                v-if="
                                    getProgressPercentage(exploration.id) >= 100
                                "
                                @click="
                                    handleCompleteExploration(exploration.id)
                                "
                                class="complete-button"
                                title="Complete Exploration"
                            >
                                <Icon icon="mdi:check-circle" class="h-5 w-5" />
                                Complete
                            </button>
                            <button
                                @click="recallDweller(exploration.id)"
                                class="recall-button"
                                title="Recall Dweller"
                            >
                                <Icon
                                    icon="mdi:arrow-u-left-top"
                                    class="h-5 w-5"
                                />
                                Recall
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <div v-else class="exploring-dwellers">
                <p class="text-xs text-gray-500">
                    <Icon icon="mdi:information" class="inline h-4 w-4" />
                    No active explorers. Drag dwellers here to send them to the
                    wasteland!
                </p>
            </div>
        </div>

        <!-- Duration Selection Modal -->
        <div v-if="showDurationModal" class="modal-overlay" @click="cancelSend">
            <div class="modal-content" @click.stop>
                <h3 class="modal-title">
                    <Icon icon="mdi:clock-outline" class="inline h-6 w-6" />
                    Select Exploration Duration
                </h3>
                <p class="modal-subtitle">
                    How long should {{ pendingDweller?.firstName }} explore?
                </p>
                <div class="duration-options">
                    <button
                        v-for="duration in [1, 2, 4, 8, 12, 24]"
                        :key="duration"
                        @click="selectedDuration = duration"
                        class="duration-button"
                        :class="{ active: selectedDuration === duration }"
                    >
                        {{ duration }}h
                    </button>
                </div>

                <div class="medical-supplies">
                    <h4 class="supply-title">
                        <Icon icon="mdi:medical-bag" class="inline h-5 w-5" />
                        Medical Supplies
                    </h4>
                    <div class="supply-inputs">
                        <div class="supply-item">
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs"
                                    >Stimpaks (Heals HP)</label
                                >
                                <span class="text-xs font-bold"
                                    >{{ selectedStimpaks }} /
                                    {{
                                        getDwellerById(
                                            pendingDweller?.dwellerId || "",
                                        )?.stimpack || 0
                                    }}</span
                                >
                            </div>
                            <input
                                type="range"
                                v-model.number="selectedStimpaks"
                                min="0"
                                :max="
                                    Math.min(
                                        getDwellerById(
                                            pendingDweller?.dwellerId || '',
                                        )?.stimpack || 0,
                                        25,
                                    )
                                "
                                class="supply-slider stimpak-slider"
                            />
                        </div>
                        <div class="supply-item">
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs"
                                    >RadAway (Removes Rads)</label
                                >
                                <span class="text-xs font-bold"
                                    >{{ selectedRadaways }} /
                                    {{
                                        getDwellerById(
                                            pendingDweller?.dwellerId || "",
                                        )?.radaway || 0
                                    }}</span
                                >
                            </div>
                            <input
                                type="range"
                                v-model.number="selectedRadaways"
                                min="0"
                                :max="
                                    Math.min(
                                        getDwellerById(
                                            pendingDweller?.dwellerId || '',
                                        )?.radaway || 0,
                                        25,
                                    )
                                "
                                class="supply-slider radaway-slider"
                            />
                        </div>
                    </div>
                    <p class="text-[10px] text-orange-400 mt-2">
                        * Selected items will be removed from dweller's
                        inventory and used automatically in the wasteland.
                    </p>
                </div>

                <div class="modal-actions">
                    <button @click="cancelSend" class="modal-button cancel">
                        <Icon icon="mdi:close" class="h-5 w-5" />
                        Cancel
                    </button>
                    <button
                        @click="confirmSendToWasteland"
                        class="modal-button confirm"
                    >
                        <Icon icon="mdi:check" class="h-5 w-5" />
                        Send to Wasteland
                    </button>
                </div>
            </div>
        </div>

        <!-- Rewards Modal -->
        <ExplorationRewardsModal
            :show="showRewardsModal"
            :rewards="completedExplorationRewards"
            :dweller-name="completedDwellerName"
            @close="closeRewardsModal"
        />
    </div>
</template>

<style scoped>
.wasteland-panel {
    position: relative;
    margin-bottom: 1rem;
}

.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 1rem;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: "Courier New", monospace;
    z-index: 1000;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.notification-success {
    background: rgba(0, 128, 0, 0.9);
    border: 2px solid var(--color-theme-primary);
    color: var(--color-theme-primary);
}

.notification-error {
    background: rgba(128, 0, 0, 0.9);
    border: 2px solid #ff0000;
    color: #ff0000;
}

.wasteland-dropzone {
    background: rgba(139, 69, 19, 0.2);
    border: 2px dashed rgba(205, 133, 63, 0.5);
    border-radius: 8px;
    padding: 1rem;
    transition: all 0.3s ease;
    min-height: 80px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    cursor: pointer;
}

.wasteland-dropzone:hover {
    border-color: rgba(205, 133, 63, 0.8);
    background: rgba(139, 69, 19, 0.3);
}

.wasteland-dropzone.drag-over {
    border-color: var(--color-theme-primary);
    border-width: 3px;
    border-style: solid;
    background: var(--color-theme-glow);
    box-shadow: 0 0 20px var(--color-theme-glow);
    transform: scale(1.02);
}

.dropzone-content {
    position: relative;
}

.dropzone-header {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.dropzone-icon {
    font-size: 2rem;
    color: rgba(205, 133, 63, 0.8);
    flex-shrink: 0;
}

.drag-over .dropzone-icon {
    color: var(--color-theme-primary);
}

.dropzone-title {
    color: rgba(205, 133, 63, 1);
    font-size: 1.125rem;
    font-weight: bold;
    font-family: "Courier New", monospace;
    margin-bottom: 0.125rem;
}

.drag-over .dropzone-title {
    color: var(--color-theme-primary);
}

.dropzone-subtitle {
    color: rgba(205, 133, 63, 0.7);
    font-size: 0.75rem;
    font-family: "Courier New", monospace;
}

.drag-over .dropzone-subtitle {
    display: none;
}

.drop-indicator {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    color: var(--color-theme-primary);
    font-size: 1rem;
    font-weight: bold;
    pointer-events: none;
}

.exploring-dwellers {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(205, 133, 63, 0.3);
}

.explorers-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.view-all-btn {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.375rem 0.75rem;
    background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
    border: 1px solid var(--color-theme-primary);
    border-radius: 4px;
    color: var(--color-theme-primary);
    font-size: 0.75rem;
    font-weight: 700;
    text-decoration: none;
    transition: all 0.2s ease;
    font-family: "Courier New", monospace;
    text-shadow: 0 0 4px var(--color-theme-glow);
}

.view-all-btn:hover {
    background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
    box-shadow: 0 0 10px var(--color-theme-glow);
    transform: translateX(2px);
}

.text-wasteland {
    color: rgba(205, 133, 63, 1);
}

.text-wasteland-dim {
    color: rgba(205, 133, 63, 0.7);
}

.explorer-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.explorer-card {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(205, 133, 63, 0.3);
    border-radius: 6px;
    padding: 0.75rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.2s ease;
}

.explorer-card:hover {
    border-color: rgba(205, 133, 63, 0.6);
    background: rgba(0, 0, 0, 0.4);
}

.explorer-info {
    flex: 1;
}

.explorer-stats {
    display: flex;
    gap: 1rem;
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: rgba(205, 133, 63, 0.8);
}

.stat-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
}

.progress-bar-container {
    width: 100%;
    height: 8px;
    background: rgba(0, 0, 0, 0.5);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 0.5rem;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(
        90deg,
        rgba(205, 133, 63, 0.6),
        rgba(205, 133, 63, 1)
    );
    border-radius: 4px;
    transition: width 0.3s ease;
}

.explorer-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.complete-button {
    background: rgba(0, 180, 0, 0.2);
    border: 2px solid var(--color-theme-primary);
    color: var(--color-theme-primary);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.875rem;
    font-weight: bold;
    transition: all 0.2s ease;
    font-family: "Courier New", monospace;
    text-shadow: 0 0 4px var(--color-theme-glow);
}

.complete-button:hover {
    background: rgba(0, 220, 0, 0.3);
    border-color: var(--color-theme-primary);
    transform: scale(1.05);
    box-shadow: 0 0 10px var(--color-theme-glow);
}

.recall-button {
    background: rgba(205, 133, 63, 0.2);
    border: 1px solid rgba(205, 133, 63, 0.5);
    color: rgba(205, 133, 63, 1);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.875rem;
    font-weight: bold;
    transition: all 0.2s ease;
    font-family: "Courier New", monospace;
}

.recall-button:hover {
    background: rgba(205, 133, 63, 0.3);
    border-color: rgba(205, 133, 63, 0.8);
    transform: scale(1.05);
}

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

.modal-content {
    background: rgba(20, 20, 20, 0.95);
    border: 2px solid rgba(205, 133, 63, 0.6);
    border-radius: 12px;
    padding: 2rem;
    max-width: 500px;
    width: 90%;
    font-family: "Courier New", monospace;
    animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
    from {
        transform: translateY(50px);
        opacity: 0;
    }
    to {
        transform: translateY(0);
        opacity: 1;
    }
}

.modal-title {
    color: rgba(205, 133, 63, 1);
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.modal-subtitle {
    color: rgba(205, 133, 63, 0.7);
    font-size: 0.875rem;
    margin-bottom: 1.5rem;
}

.duration-options {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.5rem;
}

.duration-button {
    background: rgba(205, 133, 63, 0.2);
    border: 2px solid rgba(205, 133, 63, 0.4);
    color: rgba(205, 133, 63, 1);
    padding: 0.75rem;
    border-radius: 6px;
    font-size: 1rem;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: "Courier New", monospace;
}

.duration-button:hover {
    background: rgba(205, 133, 63, 0.3);
    border-color: rgba(205, 133, 63, 0.6);
}

.duration-button.active {
    background: rgba(205, 133, 63, 0.5);
    border-color: rgba(205, 133, 63, 1);
    box-shadow: 0 0 15px rgba(205, 133, 63, 0.4);
}

.medical-supplies {
    margin-bottom: 2rem;
    padding: 1rem;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(205, 133, 63, 0.3);
    border-radius: 8px;
}

.supply-title {
    color: rgba(205, 133, 63, 1);
    font-size: 1rem;
    font-weight: bold;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.supply-inputs {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}

.supply-item {
    display: flex;
    flex-direction: column;
}

.supply-slider {
    -webkit-appearance: none;
    width: 100%;
    height: 6px;
    border-radius: 3px;
    outline: none;
    background: rgba(205, 133, 63, 0.2);
}

.stimpak-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #4caf50;
    cursor: pointer;
    box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.radaway-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #ffeb3b;
    cursor: pointer;
    box-shadow: 0 0 10px rgba(255, 235, 59, 0.5);
}

.modal-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
}

.modal-button {
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: all 0.2s ease;
    font-family: "Courier New", monospace;
    border: 2px solid;
}

.modal-button.cancel {
    background: rgba(128, 128, 128, 0.2);
    border-color: rgba(128, 128, 128, 0.5);
    color: rgba(200, 200, 200, 1);
}

.modal-button.cancel:hover {
    background: rgba(128, 128, 128, 0.3);
    border-color: rgba(128, 128, 128, 0.8);
}

.modal-button.confirm {
    background: var(--color-theme-glow);
    border-color: var(--color-theme-primary);
    color: var(--color-theme-primary);
}

.modal-button.confirm:hover {
    background: var(--color-theme-glow);
    border-color: var(--color-theme-primary);
    box-shadow: 0 0 15px var(--color-theme-glow);
}
</style>
