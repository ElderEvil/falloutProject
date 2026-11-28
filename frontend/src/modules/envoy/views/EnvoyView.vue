<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import TerminalConfirmation from '@/core/components/common/TerminalConfirmation.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { useToast } from '@/core/composables/useToast'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import TradingPostPanel from '@/modules/trading/components/TradingPostPanel.vue'
import EnvoyLog from '../components/EnvoyLog.vue'
import FilingInbox from '../components/FilingInbox.vue'
import HailDialog from '../components/HailDialog.vue'
import SignalList from '../components/SignalList.vue'
import type { EnvoyFiling, EnvoySignal } from '../models/envoy'
import { useEnvoyStore } from '../stores/envoy'

const route = useRoute()
const featureFlags = useFeatureFlagsStore()
const envoyStore = useEnvoyStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const activeTab = ref<string | number>('signals')
const hailTarget = ref<EnvoySignal | null>(null)
const responseTarget = ref<{ filing: EnvoyFiling; accept: boolean } | null>(null)

const featureOff = computed(() => featureFlags.loaded && !featureFlags.vaultDiplomacy)
const responseMessage = computed(() =>
  responseTarget.value?.accept
    ? 'Accepting opens the line and pays the first contact. Both vaults see the answer in their logs.'
    : 'Refusing locks the band for this pair until the refusal window lapses. The log keeps the refusal.'
)

/** Bumped by every sweep and by unmount, so a sweep awaiting flags cannot start a dead view. */
let sweepToken = 0

async function sweep(): Promise<void> {
  const token = ++sweepToken
  // A failed first fetch leaves flags unloaded; without this retry the guard below sticks.
  if (!featureFlags.loaded) await featureFlags.fetchFlags()
  if (token !== sweepToken || !featureFlags.vaultDiplomacy) return
  await envoyStore.start(vaultId.value)
}

function closeHail(open: boolean): void {
  if (!open) hailTarget.value = null
}

function openHail(signal: EnvoySignal): void {
  envoyStore.clearActionError()
  hailTarget.value = signal
}

function openResponse(filing: EnvoyFiling, accept: boolean): void {
  envoyStore.clearActionError()
  responseTarget.value = { filing, accept }
}

function respondFromRoster(signal: EnvoySignal, accept: boolean): void {
  const filing = envoyStore.pendingFilingFrom(signal.vault_id)
  if (filing) openResponse(filing, accept)
}

async function confirmHail(): Promise<void> {
  const target = hailTarget.value
  if (!target) return
  const filed = await envoyStore.hail(target.vault_id)
  if (!filed) return
  toast.success(`Hail filed with VAULT ${target.number}`)
  hailTarget.value = null
}

async function confirmResponse(): Promise<void> {
  const pending = responseTarget.value
  if (!pending) return
  const answered = await envoyStore.respond(pending.filing.filing_id, pending.accept)
  // A refusal keeps the dialog open so the store's reason stays on screen.
  if (!answered) return
  responseTarget.value = null
  toast.success(pending.accept ? 'Line opened' : 'Hail refused — the band is locked')
}

onMounted(() => {
  void sweep()
})

onUnmounted(() => {
  sweepToken += 1
  envoyStore.stop()
})

watch(vaultId, async () => {
  envoyStore.stop()
  // The previous vault's dialogs must not answer for the new one.
  hailTarget.value = null
  responseTarget.value = null
  await sweep()
})
</script>

<template>
  <VaultPageShell rail terminal>
    <div class="flex flex-col gap-6">
      <PageHeader
        title="ENVOY TERMINAL"
        icon="mdi:radio-tower"
        subtitle="Inter-vault relations · emergency band 47.2"
      >
        <template #actions>
          <Button
            variant="outline"
            size="sm"
            :disabled="envoyStore.loading || envoyStore.refreshing || featureOff"
            @click="sweep"
          >
            <Icon icon="mdi:refresh" :ariaHidden="true" />
            Refresh
          </Button>
        </template>
      </PageHeader>

      <TerminalEmptyState
        v-if="featureOff"
        icon="mdi:radio-tower"
        title="TERMINAL OFFLINE"
        description="Vault diplomacy is disabled on this server, so every Envoy route answers 404. The band stays silent until an operator enables vault diplomacy."
      />

      <TerminalLoadingState
        v-else-if="!featureFlags.loaded || (envoyStore.loading && !envoyStore.signals.length)"
        message="Tuning the emergency band..."
      />

      <Alert
        v-else-if="envoyStore.errorMessage && !envoyStore.signals.length"
        variant="destructive"
      >
        <Icon icon="mdi:alert-circle-outline" />
        <AlertTitle>BAND UNREADABLE</AlertTitle>
        <AlertDescription>
          {{ envoyStore.errorMessage }}
          <Button variant="secondary" size="sm" class="mt-2" @click="sweep">
            <Icon icon="mdi:refresh" :ariaHidden="true" />
            Retry sweep
          </Button>
        </AlertDescription>
      </Alert>

      <template v-else>
        <Alert v-if="envoyStore.errorMessage" variant="destructive">
          <Icon icon="mdi:alert-circle-outline" />
          <AlertTitle>LAST SWEEP FAILED</AlertTitle>
          <AlertDescription>
            {{ envoyStore.errorMessage }} The roster below is the last answer the band returned.
          </AlertDescription>
        </Alert>

        <Tabs v-model="activeTab">
          <div class="overflow-x-auto">
            <!-- @vue-ignore -->
            <TabsList aria-label="Envoy Terminal sections" class="min-w-full w-max">
              <TabsTrigger value="signals" class="min-h-11 px-3 text-xs sm:px-5 sm:text-sm">
                SIGNALS
              </TabsTrigger>
              <TabsTrigger value="inbox" class="min-h-11 px-3 text-xs sm:px-5 sm:text-sm">
                INBOX
                <Badge
                  v-if="envoyStore.pendingIncomingCount"
                  variant="outline"
                  class="border-theme-primary/40 tabular-nums text-theme-primary"
                >
                  {{ envoyStore.pendingIncomingCount }}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="labour" class="min-h-11 px-3 text-xs sm:px-5 sm:text-sm">
                LABOUR
              </TabsTrigger>
              <TabsTrigger value="log" class="min-h-11 px-3 text-xs sm:px-5 sm:text-sm">
                LOG
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="signals" class="pt-4">
            <SignalList
              :signals="envoyStore.sortedSignals"
              :awaiting="envoyStore.awaitingTargets"
              :loading="envoyStore.loading"
              :refreshing="envoyStore.refreshing"
              :busy="envoyStore.acting"
              @hail="openHail"
              @respond="respondFromRoster"
            />
          </TabsContent>

          <TabsContent value="inbox" class="pt-4">
            <FilingInbox
              :filings="envoyStore.pendingIncoming"
              :vault-label="envoyStore.vaultLabel"
              :loading="envoyStore.loading"
              :refreshing="envoyStore.refreshing"
              :busy="envoyStore.acting"
              @respond="openResponse"
            />
          </TabsContent>

          <TabsContent value="labour" class="pt-4">
            <TradingPostPanel :vault-id="vaultId" />
          </TabsContent>

          <TabsContent value="log" class="pt-4">
            <EnvoyLog
              :filings="envoyStore.filings"
              :vault-label="envoyStore.vaultLabel"
              :counterparty-of="envoyStore.counterpartyOf"
              :loading="envoyStore.loading"
              :refreshing="envoyStore.refreshing"
            />
          </TabsContent>
        </Tabs>
      </template>
    </div>

    <HailDialog
      :open="hailTarget !== null"
      :signal="hailTarget"
      :ttl-hours="envoyStore.config?.filing_ttl_hours ?? 48"
      :busy="envoyStore.acting"
      :error="envoyStore.actionError"
      @update:open="closeHail"
      @confirm="confirmHail"
    />

    <TerminalConfirmation
      :open="responseTarget !== null"
      :title="responseTarget?.accept ? 'OPEN THE LINE' : 'REFUSE THE HAIL'"
      :message="responseMessage"
      :confirm-label="responseTarget?.accept ? 'ACCEPT' : 'REFUSE'"
      :error="envoyStore.actionError"
      @confirm="confirmResponse"
      @cancel="responseTarget = null"
    />
  </VaultPageShell>
</template>
