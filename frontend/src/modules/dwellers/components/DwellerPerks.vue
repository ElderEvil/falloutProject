<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button } from '@/core/components/ui/button'
import TerminalConfirmation from '@/core/components/common/TerminalConfirmation.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerDetailContext } from './DwellerDetailContext'
import { useDwellerPerksStore } from '../stores/perks'
import type { DwellerPerk } from '../services/dwellerService'

const ctx = useDwellerDetailContext()
const store = useDwellerPerksStore()
const auth = useAuthStore()
const pending = ref<DwellerPerk | null>(null)
const pendingPerk = computed(() => store.data?.options.find((perk) => perk.id === pending.value))

function confirmChoice() {
  const perk = pending.value
  pending.value = null
  if (perk) void store.choose(perk)
}

watch(
  () => [ctx.vaultId.value, ctx.dweller.value?.id, auth.token] as const,
  ([vault, id]) => {
    pending.value = null
    void store.load(vault ?? '', id ?? '')
  },
  { immediate: true }
)
</script>

<template>
  <section
    class="space-y-4"
    aria-label="Explorer perks"
    :aria-busy="store.loading || store.selecting"
  >
    <h3 class="text-lg font-bold text-theme-primary">EXPLORER PERKS</h3>
    <p class="text-sm text-muted-foreground">
      Choose one permanent perk from level 5. Requirements use trained SPECIAL, without equipment
      bonuses.
    </p>
    <p v-if="store.loading" role="status">Loading perks…</p>
    <p v-if="store.error" role="alert" class="text-danger">{{ store.error }}</p>
    <Button
      v-if="store.error"
      variant="outline"
      @click="store.load(ctx.vaultId.value ?? '', ctx.dweller.value?.id ?? '')"
    >
      Refresh perks
    </Button>
    <article
      v-for="perk in store.data?.options ?? []"
      :key="perk.id"
      class="space-y-2 rounded border border-theme-primary/30 p-4"
    >
      <h4 class="font-bold text-theme-primary">{{ perk.name }}</h4>
      <p class="text-sm">{{ perk.description }}</p>
      <p class="text-xs text-muted-foreground">
        Level {{ perk.minimum_level }} · Trained {{ perk.stat }} {{ perk.minimum_stat }}
      </p>
      <p
        v-if="store.data?.selected_perk === perk.id"
        role="status"
        class="font-bold text-theme-primary"
      >
        Learned
      </p>
      <template v-else-if="!store.data?.selected_perk">
        <p v-if="perk.unavailable_reason" class="text-sm text-muted-foreground">
          {{ perk.unavailable_reason }}
        </p>
        <Button
          variant="outline"
          :disabled="!perk.eligible || store.selecting"
          @click="pending = perk.id"
        >
          Choose {{ perk.name }}
        </Button>
      </template>
    </article>
    <TerminalConfirmation
      :open="!!pendingPerk"
      :title="`Learn ${pendingPerk?.name ?? ''}?`"
      :message="`Learn ${pendingPerk?.name ?? ''} permanently? This uses this dweller's only perk choice.`"
      :confirm-label="`Confirm ${pendingPerk?.name ?? ''}`"
      @confirm="confirmChoice"
      @cancel="pending = null"
    />
  </section>
</template>
