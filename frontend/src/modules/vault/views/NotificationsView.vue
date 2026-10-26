<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Badge } from '@/core/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { formatRelativeTime } from '@/core/utils/time'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useNotificationInboxStore } from '@/modules/vault/stores/notificationInbox'
import { getNotificationRoute } from '@/modules/vault/utils/notificationRouting'
import type { InboxNotification, ReadFilter } from '@/modules/vault/services/notificationService'

const route = useRoute()
const router = useRouter()
const vaultStore = useVaultStore()
const inbox = useNotificationInboxStore()
const { isCollapsed } = useSidePanel()
const selectedVault = computed({
  get: () =>
    typeof route.query.vault === 'string'
      ? route.query.vault
      : (vaultStore.currentVaultId ?? 'all'),
  set: (vault: string) => {
    void router.replace({ query: { ...route.query, vault } })
  },
})
const status = computed<ReadFilter>({
  get: () =>
    route.query.status === 'read' || route.query.status === 'unread' ? route.query.status : 'all',
  set: (value) => {
    void router.replace({ query: { ...route.query, vault: selectedVault.value, status: value } })
  },
})
const vaultId = computed(() => (selectedVault.value === 'all' ? null : selectedVault.value))
const scopeLabel = computed(() =>
  vaultId.value
    ? `Vault ${vaultStore.vaults.find((vault) => vault.id === vaultId.value)?.number ?? ''}`.trim()
    : 'all vaults'
)
const hasUnread = computed(() => inbox.notifications.some((item) => !item.is_read))
const filters: { value: ReadFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: 'read', label: 'Read' },
]

function reload() {
  return inbox.load(vaultId.value, status.value)
}

function openNotification(notification: InboxNotification) {
  const destination = getNotificationRoute(notification)
  if (!destination) return
  void router.push(destination)
  if (!inbox.isRead(notification)) inbox.markReadOnOpen(notification)
}

watch([selectedVault, status], reload, { immediate: true })

onMounted(() => {
  const token = useAuthStore().token
  if (token) void vaultStore.fetchVaults(token)
})
</script>

<template>
  <div class="min-h-screen bg-terminal-background text-theme-primary [text-shadow:none]">
    <SidePanel v-if="vaultStore.currentVaultId" :vault-id="vaultStore.currentVaultId" />
    <main
      class="min-w-0 pb-8 transition-[margin-left] duration-300 max-md:ml-0"
      :class="vaultStore.currentVaultId ? (isCollapsed ? 'ml-16' : 'ml-60') : ''"
    >
      <div class="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
        <PageHeader
          title="Notifications"
          icon="mdi:inbox"
          subtitle="Your vault activity, in one place."
        >
          <template #back>
            <PageNavigation
              back-label="Back to Home"
              back-to="/"
              :breadcrumbs="[{ label: 'Home', to: '/' }, { label: 'Notifications' }]"
            />
          </template>
          <template #actions>
            <Button variant="outline" :disabled="inbox.isLoading || inbox.isSaving" @click="reload">
              <!-- @vue-ignore -->
              <Icon icon="mdi:refresh" data-icon="inline-start" /> Refresh
            </Button>
          </template>
        </PageHeader>

        <section
          aria-label="Notification filters"
          class="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-theme-primary/20 bg-surface p-4"
        >
          <div class="flex flex-wrap items-center gap-4">
            <Select
              :model-value="selectedVault"
              @update:model-value="
                (value) => {
                  if (typeof value === 'string') selectedVault = value
                }
              "
            >
              <SelectTrigger aria-label="Filter by vault" class="min-w-44"
                ><SelectValue
              /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All vaults</SelectItem>
                  <SelectItem v-for="vault in vaultStore.vaults" :key="vault.id" :value="vault.id">
                    Vault {{ vault.number }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <!-- @vue-ignore -->
            <ToggleGroup
              type="single"
              :model-value="status"
              variant="outline"
              aria-label="Read status"
              @update:model-value="
                (value) => {
                  if (value) status = value as ReadFilter
                }
              "
            >
              <ToggleGroupItem
                v-for="filter in filters"
                :key="filter.value"
                :value="filter.value"
                >{{ filter.label }}</ToggleGroupItem
              >
            </ToggleGroup>
          </div>
          <Button
            variant="ghost"
            size="sm"
            :disabled="!hasUnread || inbox.isSaving || inbox.isLoading"
            @click="inbox.markAllRead(vaultId)"
          >
            <!-- @vue-ignore -->
            <Icon icon="mdi:check-all" data-icon="inline-start" /> Mark {{ scopeLabel }} read
          </Button>
        </section>

        <div
          v-if="inbox.isLoading && !inbox.notifications.length"
          role="status"
          class="py-16 text-center text-muted-foreground"
        >
          <Icon icon="mdi:loading" class="mx-auto mb-3 size-8 animate-spin" /> Loading
          notifications…
        </div>
        <Alert v-else-if="inbox.error" variant="destructive">
          <AlertTitle>Couldn't load notifications</AlertTitle>
          <AlertDescription
            >{{ inbox.error
            }}<Button variant="link" @click="reload">Try again</Button></AlertDescription
          >
        </Alert>
        <TerminalEmptyState
          v-else-if="!inbox.notifications.length"
          icon="mdi:inbox-check-outline"
          :title="status === 'unread' ? 'All caught up' : 'No notifications here'"
          description="Activity matching your vault and read-status filters will appear here."
        />
        <section
          v-else
          aria-label="Notification history"
          :aria-busy="inbox.isLoading"
          class="overflow-hidden rounded-lg border border-theme-primary/20 bg-surface"
        >
          <article
            v-for="notification in inbox.notifications"
            :key="notification.id"
            class="flex flex-col gap-4 border-b border-theme-primary/10 p-5 last:border-b-0 sm:flex-row sm:items-start"
          >
            <Icon
              :icon="notification.is_read ? 'mdi:email-open-outline' : 'mdi:email-outline'"
              class="mt-1 size-6 shrink-0"
              :class="notification.is_read ? 'text-muted-foreground' : 'text-theme-primary'"
            />
            <div class="min-w-0 flex-1">
              <div class="mb-2 flex flex-wrap items-center gap-2">
                <Badge :variant="notification.is_read ? 'secondary' : 'default'">{{
                  notification.is_read ? 'Read' : 'Unread'
                }}</Badge>
                <Badge
                  v-if="notification.priority === 'urgent' || notification.priority === 'high'"
                  variant="outline"
                  >{{ notification.priority }}</Badge
                >
                <span class="text-xs text-muted-foreground">{{
                  notification.vault_id
                    ? `Vault ${vaultStore.vaults.find((vault) => vault.id === notification.vault_id)?.number ?? '—'}`
                    : 'System'
                }}</span>
                <time
                  :datetime="notification.created_at"
                  :title="new Date(notification.created_at).toLocaleString()"
                  class="text-xs text-muted-foreground"
                  >{{ formatRelativeTime(notification.created_at) }}</time
                >
              </div>
              <h2
                class="font-semibold"
                :class="notification.is_read ? 'text-muted-foreground' : 'text-foreground'"
              >
                {{ notification.title }}
              </h2>
              <p
                class="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground"
              >
                {{ notification.message }}
              </p>
            </div>
            <div class="flex shrink-0 flex-wrap gap-2">
              <Button
                v-if="!notification.is_read"
                size="sm"
                variant="ghost"
                :disabled="inbox.isSaving || inbox.isLoading"
                @click="inbox.markRead(notification.id)"
                >Mark read</Button
              >
              <Button
                v-if="getNotificationRoute(notification)"
                size="sm"
                variant="outline"
                :disabled="inbox.isSaving || inbox.isLoading"
                @click="openNotification(notification)"
              >
                View details
                <!-- @vue-ignore -->
                <Icon icon="mdi:arrow-right" data-icon="inline-end" />
              </Button>
            </div>
          </article>
        </section>
        <div v-if="inbox.hasMore" class="mt-6 flex justify-center">
          <Button
            variant="outline"
            :disabled="inbox.isLoading || inbox.isSaving"
            @click="inbox.load(vaultId, status, true)"
            >{{ inbox.isLoading ? 'Loading…' : 'Load older notifications' }}</Button
          >
        </div>
      </div>
    </main>
  </div>
</template>
