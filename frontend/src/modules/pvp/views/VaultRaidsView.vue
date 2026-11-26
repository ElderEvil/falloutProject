<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
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
import { formatDateTime } from '@/core/utils/format'
import { getDwellerDisplayName, type DwellerShort } from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { usePvpStore } from '../stores/pvp'

const route = useRoute()
const vaultStore = useVaultStore()
const pvpStore = usePvpStore()
const { filter: dwellerFilter } = useDwellerStore()
const toast = useToast()
const vaultId = computed(() => route.params.id as string)
const vaultLabel = computed(() => {
  const vault = vaultStore.vaults.find((candidate) => candidate.id === vaultId.value)
  return vault ? `Vault ${vault.number}` : 'Your vault'
})

const selectedIds = ref<string[]>([])
const roster = computed(() =>
  dwellerFilter.allDwellers.filter((dweller) => dweller.status !== 'dead')
)
const selectedCount = computed(() => selectedIds.value.length)
const journal = computed(() => pvpStore.displayedDuel?.journal ?? [])
const winnerName = computed(() => {
  const duel = pvpStore.displayedDuel
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

async function load(): Promise<void> {
  const id = vaultId.value
  const requestedDuel = route.query.duel
  const [loaded] = await Promise.all([
    pvpStore.load(id, typeof requestedDuel === 'string' ? requestedDuel : undefined),
    dwellerFilter.fetchAllDwellers(id),
  ])
  if (!loaded || id !== vaultId.value) return
  const rosterIds = new Set(roster.value.map((dweller) => dweller.id))
  const retained = selectedIds.value.filter((selected) => rosterIds.has(selected))
  selectedIds.value = retained.length
    ? retained
    : roster.value.slice(0, 3).map((dweller) => dweller.id)
}

async function postChallenge(): Promise<void> {
  if (!selectedCount.value || pvpStore.acting) return
  const duel = await pvpStore.post(vaultId.value, selectedIds.value)
  if (duel) toast.success('Challenge posted to the duel board')
}

async function acceptChallenge(duelId: string): Promise<void> {
  if (!selectedCount.value || pvpStore.acting) return
  const duel = await pvpStore.accept(vaultId.value, duelId, selectedIds.value)
  if (duel) toast.success('Duel settled')
}

watch([vaultId, () => route.query.duel], load, { immediate: true })
</script>

<template>
  <VaultPageShell rail terminal>
    <div class="flex flex-col gap-6">
      <PageHeader
        title="Vault Raids"
        icon="mdi:sword-cross"
        subtitle="Exhibition duels between vaults — nobody is hurt and nothing is wagered."
      >
        <template #actions>
          <Button
            variant="outline"
            size="sm"
            :disabled="pvpStore.loading || pvpStore.acting"
            @click="load"
          >
            <Icon icon="mdi:refresh" :ariaHidden="true" />
            Refresh
          </Button>
        </template>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>Your exhibition party</CardTitle>
          <CardDescription>
            Choose 1–3 dwellers from {{ vaultLabel }}. They fight from a frozen snapshot, so a duel
            cannot injure them or change their assignment.
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
              :disabled="
                pvpStore.acting || (!selectedIds.includes(dweller.id) && selectedCount >= 3)
              "
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
          <p v-if="!pvpStore.loading && !roster.length" class="text-sm text-muted-foreground">
            No living dwellers are available.
          </p>
          <div class="flex flex-wrap items-center gap-3">
            <Button
              :disabled="!selectedCount || pvpStore.hasOpenChallenge || pvpStore.acting"
              @click="postChallenge"
            >
              <Icon icon="mdi:sword" :ariaHidden="true" />
              {{ pvpStore.acting ? 'Working…' : 'Post challenge' }}
            </Button>
            <span class="text-xs text-muted-foreground">{{ selectedCount }} / 3 selected</span>
            <span v-if="pvpStore.hasOpenChallenge" class="text-xs text-muted-foreground">
              Your current challenge must settle or expire before another can be posted.
            </span>
          </div>
        </CardContent>
      </Card>

      <Card v-if="pvpStore.ownOpenDuel">
        <CardHeader>
          <CardTitle>Your open challenge</CardTitle>
          <CardDescription>
            Expires {{ formatDateTime(pvpStore.ownOpenDuel.expires_at) }}
          </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-wrap items-center gap-3">
          <Badge variant="outline" class="capitalize">
            {{ pvpStore.ownOpenDuel.challenger_party.power_band }} band
          </Badge>
          <span>{{ pvpStore.ownOpenDuel.challenger_party.member_names.join(', ') }}</span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Open challenges</CardTitle>
          <CardDescription>
            Answering settles the duel immediately. Your selected party is the defending side.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p v-if="pvpStore.loading" class="text-sm text-muted-foreground">
            Loading the duel board…
          </p>
          <p v-else-if="!pvpStore.board.length" class="text-sm text-muted-foreground">
            No challenges are waiting. Post yours for another vault to answer.
          </p>
          <ul v-else class="flex flex-col gap-3">
            <li
              v-for="entry in pvpStore.board"
              :key="entry.duel_id"
              class="flex flex-col gap-3 rounded border border-border p-3 sm:flex-row sm:items-center"
            >
              <div class="min-w-0 flex-1">
                <p class="font-bold">{{ entry.challenger_vault_name }}</p>
                <p class="text-sm text-muted-foreground">{{ entry.member_names.join(', ') }}</p>
                <p class="text-xs text-muted-foreground">
                  <span class="capitalize">{{ entry.power_band }}</span> band ·
                  {{ entry.party_size }} dwellers · expires {{ formatDateTime(entry.expires_at) }}
                </p>
              </div>
              <Button
                :disabled="!selectedCount || pvpStore.acting"
                @click="acceptChallenge(entry.duel_id)"
              >
                Accept
              </Button>
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card
        v-if="
          pvpStore.displayedDuel?.status === 'ACCEPTED' && pvpStore.displayedDuel.defender_party
        "
      >
        <CardHeader>
          <CardTitle>{{ winnerName }} wins</CardTitle>
          <CardDescription>Result and round-by-round replay from the server.</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded border border-border p-3">
              <p class="font-bold">{{ pvpStore.displayedDuel.challenger_party.vault_name }}</p>
              <p class="text-sm text-muted-foreground">
                {{ pvpStore.displayedDuel.challenger_party.member_names.join(', ') }}
              </p>
            </div>
            <div class="rounded border border-border p-3">
              <p class="font-bold">{{ pvpStore.displayedDuel.defender_party.vault_name }}</p>
              <p class="text-sm text-muted-foreground">
                {{ pvpStore.displayedDuel.defender_party.member_names.join(', ') }}
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
