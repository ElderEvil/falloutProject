<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type IncidentAftermath } from '@/modules/combat/models/incident'
import RewardCard from '@/core/components/common/RewardCard.vue'
import { Button } from '@/core/components/ui/button'
import { getRarityBorderClass, getRarityTextClass } from '@/core/models/items'

const props = defineProps<{ aftermath: IncidentAftermath; vaultId: string }>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const acting = ref<{ index: number; action: 'take' | 'sell' } | null>(null)
const isActing = computed(() => acting.value !== null)

const threatName = computed(() => props.aftermath.type.replace(/_/g, ' ').toUpperCase())
const threatIcon = computed(() => getIncidentIcon(props.aftermath.type))

const outcomeLabel = computed(() => {
  if (props.aftermath.outcome === 'victory') return 'Incident contained'
  if (props.aftermath.outcome === 'defeat') return 'Incident lost'
  return 'Incident ended'
})

const outcomeIcon = computed(() => {
  if (props.aftermath.outcome === 'victory') return 'mdi:shield-check'
  if (props.aftermath.outcome === 'defeat') return 'mdi:shield-off-outline'
  return 'mdi:help-circle-outline'
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
  <section class="flex flex-col gap-4" aria-label="Incident aftermath">
    <header class="flex items-center gap-3">
      <Icon :icon="outcomeIcon" class="h-9 w-9 shrink-0" :class="outcomeClass" />
      <div class="min-w-0">
        <h3 class="text-base font-bold" :class="outcomeClass">{{ outcomeLabel }}</h3>
        <p class="flex items-center gap-1.5 text-xs text-terminal-green-dim">
          <Icon :icon="threatIcon" class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">
            {{ threatName }}<template v-if="aftermath.roomName"> · {{ aftermath.roomName }}</template>
          </span>
        </p>
      </div>
    </header>

    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <RewardCard
        icon="mdi:star"
        label="Experience Gained"
        :value="`+${aftermath.experienceEarned} XP`"
        variant="experience"
      />
      <RewardCard
        icon="mdi:currency-usd"
        label="Bottle Caps"
        :value="String(aftermath.capsEarned)"
        variant="caps"
      />
      <RewardCard
        icon="mdi:skull"
        label="Threats Down"
        :value="String(aftermath.enemiesDefeated)"
        variant="enemies"
      />
      <RewardCard
        icon="mdi:heart-broken"
        label="Damage Taken"
        :value="String(aftermath.damageDealt)"
        variant="damage"
      />
      <RewardCard icon="mdi:counter" label="Rounds Fought" :value="String(aftermath.rounds)" />
    </div>

    <div
      v-if="lootItems.length > 0"
      class="rounded-lg border-2 border-theme-primary/40 bg-terminal-background p-3"
    >
      <h4 class="mb-2 flex items-center text-xs font-bold uppercase tracking-wide text-terminal-green-dim">
        <Icon icon="mdi:package-variant-closed-check" class="mr-1.5 h-4 w-4" />
        Recovered ({{ lootItems.length }})
      </h4>
      <ul class="flex flex-col gap-1.5">
        <li
          v-for="(item, index) in lootItems"
          :key="index"
          class="flex items-center justify-between rounded border-l-[3px] bg-terminal-background p-2"
          :class="getRarityBorderClass(item.rarity)"
        >
          <span
            class="flex items-center gap-2 text-xs font-semibold"
            :class="getRarityTextClass(item.rarity)"
          >
            <Icon icon="mdi:treasure-chest" class="h-4 w-4" />
            {{ item.name }}
          </span>
          <span class="text-xs text-terminal-green-dim">x{{ item.quantity ?? 1 }}</span>
        </li>
      </ul>
    </div>

    <div v-if="heldItems.length > 0" class="rounded-lg border-2 border-warning/50 bg-terminal-background p-3">
      <h4 class="mb-1 flex items-center text-xs font-bold uppercase tracking-wide text-warning">
        <Icon icon="mdi:package-variant-closed-remove" class="mr-1.5 h-4 w-4" />
        Held — Storage Full ({{ heldItems.length }})
      </h4>
      <p class="mb-2 text-xs text-terminal-green-dim">
        Take them once you have room, or sell them for caps.
      </p>
      <ul class="flex flex-col gap-1.5">
        <li
          v-for="(item, index) in heldItems"
          :key="index"
          class="flex items-center justify-between gap-2 rounded border-l-[3px] bg-terminal-background p-2"
          :class="getRarityBorderClass(item.rarity)"
        >
          <span
            class="flex min-w-0 items-center gap-2 text-xs font-semibold"
            :class="getRarityTextClass(item.rarity)"
          >
            <Icon icon="mdi:package-variant-closed" class="h-4 w-4 shrink-0" />
            <span class="truncate">{{ item.name }}</span>
            <span v-if="(item.quantity ?? 1) > 1" class="text-terminal-green-dim">x{{ item.quantity }}</span>
          </span>
          <span class="flex shrink-0 gap-1">
            <Button
              variant="secondary"
              size="sm"
              :disabled="isActing"
              @click="act(index, 'take')"
            >
              <Icon
                v-if="acting?.index === index && acting?.action === 'take'"
                icon="mdi:loading"
                class="mr-1 animate-spin"
              />
              Take
            </Button>
            <Button
              variant="secondary"
              size="sm"
              :disabled="isActing"
              @click="act(index, 'sell')"
            >
              <Icon
                v-if="acting?.index === index && acting?.action === 'sell'"
                icon="mdi:loading"
                class="mr-1 animate-spin"
              />
              Sell
            </Button>
          </span>
        </li>
      </ul>
    </div>

    <p
      v-if="aftermath.outcome === 'unknown'"
      class="flex items-start gap-1.5 text-xs text-terminal-green-dim"
    >
      <Icon icon="mdi:help-circle-outline" class="mt-0.5 h-4 w-4 shrink-0" />
      The outcome was not reported — the vault was out of contact when this incident ended.
    </p>

    <Button variant="secondary" size="sm" class="w-full" @click="dismiss">Dismiss</Button>
  </section>
</template>
