<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import UButton from '@/core/components/ui/UButton.vue'
import DwellerCard from './cards/DwellerCard.vue'
import DwellerPanel from './DwellerPanel.vue'
import DwellerStatusBadge from './stats/DwellerStatusBadge.vue'
import { RevivalSection } from './death'
import { useDwellerDetailContext } from './DwellerDetailContext'

const ctx = useDwellerDetailContext()

const dweller = computed(() => ctx.dweller.value!)
const isDead = computed(() => dweller.value.is_dead === true)
const isPermanentlyDead = computed(() => !!dweller.value.is_permanently_dead)
const breadcrumbs = computed(() => [
  { label: 'Vault', to: `/vault/${ctx.vaultId.value}` },
  { label: 'Dwellers', to: `/vault/${ctx.vaultId.value}/dwellers` },
  { label: `${dweller.value.first_name} ${dweller.value.last_name ?? ''}`.trim() },
])
</script>

<template>
  <div class="dweller-detail">
    <!-- Header -->
    <div class="detail-header">
      <PageNavigation
        back-label="Back to Dwellers"
        :back-to="`/vault/${ctx.vaultId.value}/dwellers`"
        :breadcrumbs="breadcrumbs"
      />

      <div class="header-info">
        <div class="name-section">
          <h1 class="dweller-name cursor-pointer select-none" @click="ctx.actions.onHeaderNameClick()">
            {{ dweller.first_name }} {{ dweller.last_name }}
          </h1>
          <UButton
            v-if="!isDead"
            @click="ctx.actions.openRenameDialog()"
            variant="ghost"
            size="sm"
            class="rename-btn"
          >
            <Icon icon="mdi:pencil" class="h-4 w-4" />
          </UButton>
          <UButton
            v-if="!isDead"
            @click="ctx.actions.openSoftDeleteDialog()"
            variant="ghost"
            size="sm"
            class="soft-delete-btn"
            title="Soft-delete this dweller (makes them tradable at the Trading Post)"
            aria-label="Soft-delete dweller"
          >
            <Icon icon="mdi:account-remove" class="h-4 w-4" />
          </UButton>
        </div>
        <DwellerStatusBadge :status="dweller.status" :show-label="true" size="large" />
      </div>
    </div>

    <!-- Two-Column Layout -->
    <div class="detail-layout">
      <!-- Left Column: Dweller Card -->
      <div class="space-y-6">
        <DwellerCard
          :dweller="dweller"
          :image-url="dweller.image_url"
          :loading="ctx.cardLoading.value"
          :generating-portrait="ctx.generatingPortrait.value"
          :available-stimpaks="ctx.availableStimpaks.value"
          :available-radaways="ctx.availableRadaways.value"
          :issuing-medical-supply="ctx.issuingMedicalSupply.value"
          :using-stimpak="ctx.usingStimpak.value"
          :using-rad-away="ctx.usingRadAway.value"
          @chat="ctx.actions.navigateToChat()"
          @assign="ctx.actions.assign()"
          @unassign="ctx.actions.unassign()"
          @recall="ctx.actions.recall()"
          @use-stimpak="ctx.actions.useStimpak()"
          @use-radaway="ctx.actions.useRadAway()"
          @train="ctx.trainingModalOpen.value = true"
          @send-wasteland="ctx.actions.openSendToWasteland()"
          @generate-portrait="ctx.actions.generatePortrait()"
          @issue-medical-supply="ctx.actions.issueMedicalSupply($event)"
        />

        <!-- Revival Section for Dead Dwellers -->
        <RevivalSection
          v-if="isDead && !isPermanentlyDead"
          :dweller-id="dweller.id"
          :revival-cost="ctx.revivalCost.value"
          :loading="ctx.revivalLoading.value"
          @revive="ctx.actions.revive()"
        />

        <!-- Permanently Dead Notice -->
        <div
          v-else-if="isPermanentlyDead"
          class="bg-gray-900 border border-red-500/30 rounded-lg p-4 text-center"
        >
          <Icon icon="mdi:grave-stone" class="h-12 w-12 text-gray-500 mx-auto mb-3" />
          <h3 class="text-lg font-bold text-red-500 mb-1">Permanently Deceased</h3>
          <p class="text-gray-400 text-sm">
            This dweller has passed beyond the revival window.
          </p>
          <p v-if="dweller.epitaph" class="text-theme-primary/60 italic mt-3 text-sm">
            "{{ dweller.epitaph }}"
          </p>
        </div>
      </div>

      <!-- Right Column: Dweller Panel -->
      <DwellerPanel />
    </div>
  </div>
</template>

<style scoped>
.dweller-detail {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.name-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.dweller-name {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
  letter-spacing: -0.5px;
}

.rename-btn {
  opacity: 0.6;
  transition: opacity 0.2s;
}

.soft-delete-btn {
  opacity: 0.6;
  transition: opacity 0.2s;
  color: var(--color-danger);
}

.soft-delete-btn:hover {
  opacity: 1;
}

.rename-btn:hover {
  opacity: 1;
}

.detail-layout {
  display: grid;
  grid-template-columns: minmax(340px, 400px) minmax(0, 1fr);
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1280px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
