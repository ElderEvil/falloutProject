<script setup lang="ts">
/**
 * PageHeader — unified page header for vault views.
 *
 * Provides consistent title, icon, subtitle, vault-number prefix, and slots
 * for back navigation and action buttons.
 *
 * @example
 * <PageHeader
 *   title="Dwellers"
 *   :vault-number="currentVault?.number"
 *   icon="mdi:account-group"
 *   subtitle="Manage your vault population"
 * >
 *   <template #actions>
 *     <UButton size="sm">Action</UButton>
 *   </template>
 *   <template #back>
 *     <UButton variant="ghost" size="sm" @click="goBack">← Back</UButton>
 *   </template>
 * </PageHeader>
 */
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { Icon } from '@iconify/vue'

interface Props {
  /** Page title text */
  title: string
  /** Optional subtitle shown below the title */
  subtitle?: string
  /** Iconify icon name (e.g. 'mdi:account-group') */
  icon?: string
  /** Vault number to prepend — shows "Vault {n} {title}" */
  vaultNumber?: number | string | null
  /** Show the vault-number prefix (default: false) */
  showVaultNumber?: boolean
  /** Center-align the header (default: left-aligned) */
  centered?: boolean
  /** Enable glow effect on the title (default: true) */
  glow?: boolean
}

withDefaults(defineProps<Props>(), {
  glow: true,
  centered: false,
  vaultNumber: null,
  showVaultNumber: false,
})

defineSlots<{
  /** Back navigation link/button rendered above the header row */
  back?: () => unknown
  /** Right-aligned actions (buttons, badges, stats) */
  actions?: () => unknown
}>()

const { glowClass } = useVisualEffects()
</script>

<template>
  <div :class="['page-header mb-8', { 'text-center': centered }]">
    <!-- Back slot -->
    <div v-if="$slots.back" class="mb-4">
      <slot name="back" />
    </div>

    <div :class="['flex', centered ? 'flex-col items-center' : 'items-start justify-between']">
      <!-- Left: icon + text -->
      <div :class="['flex', centered ? 'flex-col items-center' : 'items-center gap-4']">
        <Icon
          v-if="icon"
          :icon="icon"
          class="text-theme-primary shrink-0"
          :class="centered ? 'w-12 h-12 mb-2' : 'w-10 h-10 md:w-12 md:h-12'"
        />
        <div :class="centered ? 'text-center' : ''">
          <h1
            class="text-3xl md:text-4xl font-bold font-mono tracking-wider leading-tight text-theme-primary"
            :class="glow ? glowClass : ''"
          >
            <template v-if="showVaultNumber && vaultNumber">
              <span class="text-theme-accent">Vault {{ vaultNumber }}</span>
              {{ ' ' }}
            </template>
            {{ title }}
          </h1>
          <p
            v-if="subtitle"
            class="text-sm mt-1 leading-relaxed"
            :class="centered ? 'text-theme-primary/60' : 'text-gray-400'"
          >
            {{ subtitle }}
          </p>
        </div>
      </div>

      <!-- Right: actions slot -->
      <div
        v-if="$slots.actions"
        :class="['flex items-center gap-2 shrink-0', centered ? 'mt-4' : '']"
      >
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
