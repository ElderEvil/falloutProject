<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type IncidentAftermath } from '@/modules/combat/models/incident'
import UButton from '@/core/components/ui/UButton.vue'

const props = defineProps<{ aftermath: IncidentAftermath; vaultId: string }>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const acting = ref<{ index: number; action: 'take' | 'sell' } | null>(null)
const isActing = computed(() => acting.value !== null)

const threatName = computed(() => props.aftermath.type.replace(/_/g, ' ').toUpperCase())
const icon = computed(() => getIncidentIcon(props.aftermath.type))

const outcomeLabel = computed(() => {
  if (props.aftermath.outcome === 'victory') return 'INCIDENT CONTAINED'
  if (props.aftermath.outcome === 'defeat') return 'INCIDENT LOST'
  return 'INCIDENT ENDED'
})

const outcomeClass = computed(() => {
  if (props.aftermath.outcome === 'victory') return 'text-terminal-green'
  if (props.aftermath.outcome === 'defeat') return 'text-danger'
  return 'text-terminal-green-dim'
})

const lootItems = computed(() => props.aftermath.loot?.items ?? [])
const heldItems = computed(() => props.aftermath.unclaimed ?? [])

const act = async (index: number, action: 'take' | 'sell') => {
  if (!authStore.token || acting.value) return
  acting.value = { index, action }
  try {
    const { vaultId, aftermath } = props
    if (action === 'take') {
      await incidentStore.takeOverflow(vaultId, aftermath.incidentId, index, authStore.token)
    } else {
      await incidentStore.sellOverflow(vaultId, aftermath.incidentId, index, authStore.token)
    }
  } finally {
    acting.value = null
  }
}

const dismiss = () => incidentStore.clearAftermath(props.aftermath.roomId)
</script>

<template>
  <section class="flex flex-col gap-3" aria-label="Incident aftermath">
    <header class="flex items-center gap-3">
      <Icon :icon="icon" class="h-8 w-8 shrink-0 text-terminal-green-dim" />
      <div>
        <h3 class="text-base font-semibold" :class="outcomeClass">{{ outcomeLabel }}</h3>
        <p class="text-xs text-terminal-green-dim">
          {{ threatName }}<template v-if="aftermath.roomName"> · {{ aftermath.roomName }}</template>
        </p>
      </div>
    </header>

    <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
      <div>
        <dt class="text-terminal-green-dim">CAPS</dt>
        <dd class="tabular-nums text-terminal-green">{{ aftermath.capsEarned }}</dd>
      </div>
      <div>
        <dt class="text-terminal-green-dim">THREATS DOWN</dt>
        <dd class="tabular-nums text-terminal-green">{{ aftermath.enemiesDefeated }}</dd>
      </div>
      <div>
        <dt class="text-terminal-green-dim">DAMAGE DEALT</dt>
        <dd class="tabular-nums text-terminal-green">{{ aftermath.damageDealt }}</dd>
      </div>
      <div>
        <dt class="text-terminal-green-dim">ROUNDS</dt>
        <dd class="tabular-nums text-terminal-green">{{ aftermath.rounds }}</dd>
      </div>
    </dl>

    <div v-if="lootItems.length">
      <p class="text-xs text-terminal-green-dim">RECOVERED</p>
      <ul class="mt-1 flex flex-col gap-0.5">
        <li v-for="(item, index) in lootItems" :key="index" class="text-xs text-terminal-green">
          {{ item.quantity && item.quantity > 1 ? `${item.quantity}× ` : '' }}{{ item.name }}
        </li>
      </ul>
    </div>

    <div v-if="heldItems.length">
      <p class="text-xs text-warning">HELD — STORAGE FULL</p>
      <ul class="mt-1 flex flex-col gap-1">
        <li
          v-for="(item, index) in heldItems"
          :key="index"
          class="flex items-center justify-between gap-2 text-xs text-terminal-green"
        >
          <span>
            {{ item.quantity && item.quantity > 1 ? `${item.quantity}× ` : '' }}{{ item.name }}
          </span>
          <span class="flex shrink-0 gap-1">
            <UButton
              variant="secondary"
              size="sm"
              :disabled="isActing"
              :loading="acting?.index === index && acting?.action === 'take'"
              @click="act(index, 'take')"
            >
              TAKE
            </UButton>
            <UButton
              variant="secondary"
              size="sm"
              :disabled="isActing"
              :loading="acting?.index === index && acting?.action === 'sell'"
              @click="act(index, 'sell')"
            >
              SELL
            </UButton>
          </span>
        </li>
      </ul>
    </div>

    <p v-if="aftermath.outcome === 'unknown'" class="text-xs text-terminal-green-dim">
      The outcome was not reported — the vault was out of contact when this incident ended.
    </p>

    <UButton variant="secondary" size="sm" block @click="dismiss">DISMISS</UButton>
  </section>
</template>
