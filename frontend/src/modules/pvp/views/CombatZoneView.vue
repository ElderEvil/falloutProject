<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useLocalStorage } from '@vueuse/core'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'
import { parseUtcMs } from '@/core/utils/time'
import { getDwellerDisplayName, type DwellerShort } from '@/modules/dwellers/models/dweller'
import { getDwellersByVault } from '@/modules/dwellers/services/dwellerService'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { pvpDuelApi, type PvpDuel } from '../api/pvpDuels'

const route = useRoute()
const vaultStore = useVaultStore()
const toast = useToast()
const openDuelIds = useLocalStorage<Record<string, string>>('pvp:open-duel-ids', {})
const vaultId = computed(() => route.params.id as string)
const vaultLabel = computed(() => {
  const vault = vaultStore.vaults.find((candidate) => candidate.id === vaultId.value)
  return vault ? `Vault ${vault.number}` : 'Your vault'
})

const roster = ref<DwellerShort[]>([])
const selectedIds = ref<string[]>([])
const board = ref<Awaited<ReturnType<typeof pvpDuelApi.list>>>([])
const currentDuel = ref<PvpDuel | null>(null)
const activeDuel = ref<PvpDuel | null>(null)
const loading = ref(true)
const acting = ref(false)
let loadVersion = 0

const selectedCount = computed(() => selectedIds.value.length)
const hasOpenChallenge = computed(() => currentDuel.value?.status === 'OPEN')
const journal = computed(() => activeDuel.value?.journal ?? [])
const winnerName = computed(() => {
  const duel = activeDuel.value
  if (!duel?.outcome) return ''
  return duel.outcome === 'challenger'
    ? duel.challenger_party.vault_name
    : duel.defender_party?.vault_name
})

function dwellerName(dweller: DwellerShort): string {
  return getDwellerDisplayName(dweller) || 'Unnamed dweller'
}

function toggleDweller(id: string): void {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((selected) => selected !== id)
  } else if (selectedIds.value.length < 3) {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function formatExpiry(value: string): string {
  return new Date(parseUtcMs(value)).toLocaleString()
}

async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  try {
    if (!vaultStore.vaults.length) await vaultStore.fetchVaults()
    const id = vaultId.value
    const [dwellers, entries] = await Promise.all([getDwellersByVault(id), pvpDuelApi.list(id)])
    if (version !== loadVersion) return
    roster.value = dwellers.filter((dweller) => dweller.status !== 'dead')
    const rosterIds = new Set(roster.value.map((dweller) => dweller.id))
    const retained = selectedIds.value.filter((selected) => rosterIds.has(selected))
    selectedIds.value = retained.length
      ? retained
      : roster.value.slice(0, 3).map((dweller) => dweller.id)
    board.value = entries
    const requestedDuel = route.query.duel
    const fromNotification = typeof requestedDuel === 'string'
    const duelId = fromNotification ? requestedDuel : openDuelIds.value[id]
    activeDuel.value = duelId ? await pvpDuelApi.get(id, duelId) : null
    currentDuel.value =
      !fromNotification && activeDuel.value?.status === 'OPEN' ? activeDuel.value : null
    if (!fromNotification) {
      if (currentDuel.value) openDuelIds.value[id] = currentDuel.value.duel_id
      else delete openDuelIds.value[id]
    }
  } catch (error) {
    handleStoreError(error, 'Failed to load The Pit')
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

async function postChallenge(): Promise<void> {
  if (!selectedCount.value || acting.value) return
  acting.value = true
  try {
    const duel = await pvpDuelApi.post(vaultId.value, selectedIds.value)
    currentDuel.value = duel
    activeDuel.value = duel
    openDuelIds.value[vaultId.value] = duel.duel_id
    toast.success('Challenge posted to the duel board')
  } catch (error) {
    handleStoreError(error, 'Failed to post the challenge')
  } finally {
    acting.value = false
  }
}

async function acceptChallenge(duelId: string): Promise<void> {
  if (!selectedCount.value || acting.value) return
  acting.value = true
  try {
    activeDuel.value = await pvpDuelApi.accept(vaultId.value, duelId, selectedIds.value)
    if (openDuelIds.value[vaultId.value] === duelId) delete openDuelIds.value[vaultId.value]
    board.value = board.value.filter((entry) => entry.duel_id !== duelId)
    toast.success('Duel settled')
  } catch (error) {
    handleStoreError(error, 'Failed to accept the challenge')
  } finally {
    acting.value = false
  }
}

watch([vaultId, () => route.query.duel], load, { immediate: true })
</script>

<template>
  <VaultPageShell rail terminal>
    <div class="flex flex-col gap-6">
      <PageHeader
        title="The Pit"
        icon="mdi:sword-cross"
        subtitle="Cross-vault exhibition duels using frozen party snapshots"
      >
        <template #actions>
          <Button variant="outline" size="sm" :disabled="loading || acting" @click="load">
            <Icon icon="mdi:refresh" :ariaHidden="true" />
            Refresh
          </Button>
        </template>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>Your exhibition party</CardTitle>
          <CardDescription>
            Choose 1–3 dwellers from {{ vaultLabel }}. Duels do not injure dwellers or grant
            rewards.
          </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-4">
          <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <Button
              v-for="dweller in roster"
              :key="dweller.id"
              :variant="selectedIds.includes(dweller.id) ? 'default' : 'outline'"
              class="h-auto justify-start px-3 py-2 text-left"
              :aria-pressed="selectedIds.includes(dweller.id)"
              :disabled="acting || (!selectedIds.includes(dweller.id) && selectedCount >= 3)"
              @click="toggleDweller(dweller.id)"
            >
              <span class="flex min-w-0 flex-col">
                <span class="truncate">{{ dwellerName(dweller) }}</span>
                <span class="text-xs font-normal opacity-70">
                  Level {{ dweller.level }} · Power {{ dweller.combat_power ?? 0 }}
                </span>
              </span>
            </Button>
          </div>
          <p v-if="!loading && !roster.length" class="text-sm text-muted-foreground">
            No living dwellers are available.
          </p>
          <div class="flex flex-wrap items-center gap-3">
            <Button :disabled="!selectedCount || hasOpenChallenge || acting" @click="postChallenge">
              <Icon icon="mdi:sword" :ariaHidden="true" />
              {{ acting ? 'Working…' : 'Post challenge' }}
            </Button>
            <span class="text-xs text-muted-foreground">{{ selectedCount }} / 3 selected</span>
            <span v-if="hasOpenChallenge" class="text-xs text-muted-foreground">
              Your current challenge must settle or expire before another can be posted.
            </span>
          </div>
        </CardContent>
      </Card>

      <Card v-if="currentDuel">
        <CardHeader>
          <CardTitle>Your open challenge</CardTitle>
          <CardDescription> Expires {{ formatExpiry(currentDuel.expires_at) }} </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-wrap items-center gap-3">
          <Badge variant="outline">{{ currentDuel.challenger_party.power_band }}</Badge>
          <span>{{ currentDuel.challenger_party.member_names.join(', ') }}</span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Open challenges</CardTitle>
          <CardDescription>Accepting settles the duel immediately on the server.</CardDescription>
        </CardHeader>
        <CardContent>
          <p v-if="loading" class="text-sm text-muted-foreground">Loading the duel board…</p>
          <p v-else-if="!board.length" class="text-sm text-muted-foreground">
            No challenges are waiting. Post yours for another vault to answer.
          </p>
          <ul v-else class="flex flex-col gap-3">
            <li
              v-for="entry in board"
              :key="entry.duel_id"
              class="flex flex-col gap-3 rounded border border-border p-3 sm:flex-row sm:items-center"
            >
              <div class="min-w-0 flex-1">
                <p class="font-bold">{{ entry.challenger_vault_name }}</p>
                <p class="text-sm text-muted-foreground">{{ entry.member_names.join(', ') }}</p>
                <p class="text-xs text-muted-foreground">
                  {{ entry.power_band }} · {{ entry.party_size }} fighters · expires
                  {{ formatExpiry(entry.expires_at) }}
                </p>
              </div>
              <Button :disabled="!selectedCount || acting" @click="acceptChallenge(entry.duel_id)">
                Accept
              </Button>
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card v-if="activeDuel?.status === 'ACCEPTED' && activeDuel.defender_party">
        <CardHeader>
          <CardTitle>{{ winnerName }} wins</CardTitle>
          <CardDescription>Authoritative result and replay from the server.</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded border border-border p-3">
              <p class="font-bold">{{ activeDuel.challenger_party.vault_name }}</p>
              <p class="text-sm text-muted-foreground">
                {{ activeDuel.challenger_party.member_names.join(', ') }}
              </p>
            </div>
            <div class="rounded border border-border p-3">
              <p class="font-bold">{{ activeDuel.defender_party.vault_name }}</p>
              <p class="text-sm text-muted-foreground">
                {{ activeDuel.defender_party.member_names.join(', ') }}
              </p>
            </div>
          </div>
          <ol class="max-h-72 overflow-y-auto rounded border border-border bg-muted p-3 text-sm">
            <li v-for="(entry, index) in journal" :key="index" class="flex gap-3">
              <span class="shrink-0 tabular-nums text-muted-foreground">
                {{ String(entry.round_seq).padStart(2, '0') }}
              </span>
              <span>{{ entry.message }}</span>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  </VaultPageShell>
</template>
