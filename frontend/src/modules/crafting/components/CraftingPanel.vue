<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UCard, UProgressBar } from '@/core/components/ui'
import { getRarityTextClass } from '@/core/models/items'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { craftingService } from '../services/craftingService'
import type { CraftableItemType, CraftingOrder, CraftingRecipe } from '../models/crafting'

interface Props {
  vaultId: string
  itemType: CraftableItemType
}

const props = defineProps<Props>()

const emit = defineEmits<{
  crafted: []
}>()

const toast = useToast()

const recipes = ref<CraftingRecipe[]>([])
const orders = ref<CraftingOrder[]>([])
const isLoading = ref(false)
const busyKey = ref<string | null>(null)
const now = ref(Date.now())
let loadSequence = 0
let ticker: number | null = null
let lastRecheck = 0
const RECHECK_MS = 5000

const itemIcon = computed(() => (props.itemType === 'weapon' ? 'mdi:sword-cross' : 'mdi:tshirt-crew'))
const workshopLabel = computed(() => (props.itemType === 'weapon' ? 'Weapon workshop' : 'Outfit workshop'))

const STAT_META: Record<string, { icon: string, label: string }> = {
  strength: { icon: 'mdi:arm-flex', label: 'STR' },
  perception: { icon: 'mdi:eye', label: 'PER' },
  endurance: { icon: 'mdi:heart', label: 'END' },
  charisma: { icon: 'mdi:account-voice', label: 'CHA' },
  intelligence: { icon: 'mdi:brain', label: 'INT' },
  agility: { icon: 'mdi:run-fast', label: 'AGI' },
  luck: { icon: 'mdi:clover', label: 'LUK' },
}

const statMeta = (stat: string) =>
  STAT_META[stat.toLowerCase()] ?? { icon: 'mdi:star', label: stat.toUpperCase() }
const craftableCount = computed(() => recipes.value.filter(recipe => recipe.can_craft).length)
const queue = computed(() =>
  orders.value.filter(order => order.status !== 'collected' && order.item_type === props.itemType),
)

function remainingSeconds(order: CraftingOrder): number {
  if (order.status !== 'active') return 0
  const endsAt = new Date(`${order.estimated_completion_at}Z`).getTime()
  return Math.max(0, Math.round((endsAt - now.value) / 1000))
}

function remainingLabel(order: CraftingOrder): string {
  if (order.status === 'completed') return 'Ready to collect'
  const seconds = remainingSeconds(order)
  if (seconds <= 0) return 'Waiting for the vault clock…'
  if (seconds >= 60) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${seconds}s`
}

// Live bar so the queue visibly fills between ticks, matching the training cards.
function progressPercent(order: CraftingOrder): number {
  const started = new Date(`${order.started_at}Z`).getTime()
  const endsAt = new Date(`${order.estimated_completion_at}Z`).getTime()
  const total = endsAt - started
  const live = total > 0 ? ((now.value - started) / total) * 100 : 0
  return Math.min(100, Math.max(order.progress * 100, live))
}

async function loadAll() {
  if (!props.vaultId) return
  const sequence = ++loadSequence
  isLoading.value = true
  try {
    const [loadedRecipes, loadedOrders] = await Promise.all([
      craftingService.listRecipes(props.vaultId, props.itemType),
      craftingService.listOrders(props.vaultId),
    ])
    if (sequence !== loadSequence) return
    recipes.value = loadedRecipes
    orders.value = loadedOrders
  } catch (error) {
    if (sequence !== loadSequence) return
    toast.error(getErrorMessage(error) || 'Failed to load the workshop')
    recipes.value = []
    orders.value = []
  } finally {
    if (sequence === loadSequence) isLoading.value = false
  }
}

async function handleStart(recipe: CraftingRecipe) {
  if (!props.vaultId || busyKey.value) return
  busyKey.value = recipe.name
  try {
    const order = await craftingService.startOrder(props.vaultId, recipe.name, props.itemType)
    toast.success(`Queued ${order.item_name} (${order.junk_spent} materials, ${order.caps_spent} caps)`)
    await loadAll()
    emit('crafted')
  } catch (error) {
    toast.error(getErrorMessage(error) || `Failed to queue ${recipe.name}`)
  } finally {
    busyKey.value = null
  }
}

async function handleCollect(order: CraftingOrder) {
  if (!props.vaultId || busyKey.value) return
  busyKey.value = order.id
  try {
    const result = await craftingService.collectOrder(props.vaultId, order.id)
    toast.success(`Crafted ${result.name}`)
    await loadAll()
    emit('crafted')
  } catch (error) {
    toast.error(getErrorMessage(error) || `Failed to collect ${order.item_name}`)
  } finally {
    busyKey.value = null
  }
}

function costLabel(recipe: CraftingRecipe): string {
  const parts = [`${recipe.junk_cost} junk`]
  if (recipe.caps_cost > 0) parts.push(`${recipe.caps_cost} caps`)
  return parts.join(' · ')
}

onMounted(() => {
  loadAll()
  ticker = window.setInterval(() => {
    now.value = Date.now()
    // The game tick flips an order to completed server-side; re-poll once its
    // timer has elapsed so Collect appears without closing the panel.
    if (Date.now() - lastRecheck > RECHECK_MS && queue.value.some(order => remainingSeconds(order) === 0 && order.status === 'active')) {
      lastRecheck = Date.now()
      loadAll()
    }
  }, 1000)
})

onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})

watch(() => [props.vaultId, props.itemType], loadAll)
</script>

<template>
  <UCard padding="sm" class="crafting-panel font-mono">
    <div class="mb-3 flex items-center gap-3 border-b border-theme-primary/30 pb-2">
      <Icon :icon="itemIcon" class="h-5 w-5 shrink-0 text-theme-primary" />
      <span class="text-xs font-semibold uppercase tracking-wider text-theme-primary">
        {{ workshopLabel }}
      </span>
      <span class="ml-auto text-xs text-theme-accent/80">
        {{ craftableCount }}/{{ recipes.length }} craftable
      </span>
    </div>

    <p v-if="isLoading" class="py-6 text-center text-sm text-theme-primary/70">Loading schematics…</p>

    <template v-else>
      <section v-if="queue.length > 0" class="mb-3">
        <h4 class="mb-2 text-[0.7rem] font-bold uppercase tracking-widest text-theme-primary/70">Queue</h4>
        <ul class="space-y-2">
          <li
            v-for="order in queue"
            :key="order.id"
            class="rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
            :class="{ 'queue-ready': order.status === 'completed' }"
          >
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-bold" :class="getRarityTextClass(order.rarity)">
                {{ order.item_name }}
              </span>
              <span class="flex shrink-0 items-center gap-1 text-xs text-theme-accent/80">
                <Icon :icon="statMeta(order.required_stat).icon" class="h-3.5 w-3.5" />
                {{ statMeta(order.required_stat).label }} {{ order.ability_sum_at_start }}
              </span>
              <span class="ml-auto shrink-0 text-xs text-theme-primary/70">{{ remainingLabel(order) }}</span>
            </div>
            <div class="mt-1.5 flex items-center gap-2">
              <UProgressBar :model-value="progressPercent(order)" :height="6" :glow="false" />
              <span class="w-9 shrink-0 text-right text-xs text-theme-primary">
                {{ progressPercent(order).toFixed(0) }}%
              </span>
              <UButton
                v-if="order.status === 'completed'"
                variant="primary"
                size="sm"
                class="shrink-0"
                :disabled="busyKey !== null"
                @click="handleCollect(order)"
              >
                <Icon
                  :icon="busyKey === order.id ? 'mdi:loading' : 'mdi:package-down'"
                  class="h-4 w-4"
                  :class="{ 'animate-spin': busyKey === order.id }"
                />
                Collect
              </UButton>
            </div>
          </li>
        </ul>
      </section>

      <p v-if="recipes.length === 0" class="py-6 text-center text-sm text-theme-primary/70">
        No craftable {{ itemType }}s are catalogued.
      </p>

      <ul v-else class="max-h-64 space-y-2 overflow-y-auto pr-1">
        <li
          v-for="recipe in recipes"
          :key="recipe.name"
          class="flex items-center gap-3 rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-bold" :class="getRarityTextClass(recipe.rarity)">
                {{ recipe.name }}
              </span>
              <span class="shrink-0 text-[0.65rem] uppercase tracking-wider text-theme-primary/50">
                {{ recipe.rarity }}
              </span>
            </div>
            <div class="mt-0.5 flex items-center gap-2 text-xs text-theme-primary/70">
              <Icon icon="mdi:wrench" class="h-3.5 w-3.5 shrink-0" />
              <span>{{ costLabel(recipe) }}</span>
              <span v-if="recipe.missing_junk > 0" class="text-danger/80">
                (missing {{ recipe.missing_junk }} scrap)
              </span>
              <span class="ml-auto flex shrink-0 items-center gap-1 text-theme-accent/80">
                <Icon :icon="statMeta(recipe.stat).icon" class="h-3.5 w-3.5" />
                {{ statMeta(recipe.stat).label }}
              </span>
            </div>
          </div>
          <UButton
            variant="primary"
            size="sm"
            class="shrink-0"
            :disabled="!recipe.can_craft || busyKey !== null"
            :title="recipe.can_craft ? `Queue ${recipe.name}` : 'Not enough materials'"
            @click="handleStart(recipe)"
          >
            <Icon
              :icon="busyKey === recipe.name ? 'mdi:loading' : 'mdi:hammer'"
              class="h-4 w-4"
              :class="{ 'animate-spin': busyKey === recipe.name }"
            />
            Start
          </UButton>
        </li>
      </ul>

      <p class="mt-2 text-[0.7rem] text-theme-primary/50">
        Materials come from scrapping gear and wasteland salvage. Dwellers working the workshop finish orders
        faster.
      </p>
    </template>
  </UCard>
</template>

<style scoped>
.crafting-panel {
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.queue-ready {
  border-color: color-mix(in srgb, var(--color-theme-accent) 60%, transparent);
}
</style>
