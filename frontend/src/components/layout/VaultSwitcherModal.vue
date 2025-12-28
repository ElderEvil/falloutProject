<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'

interface Props {
  modelValue: boolean
  currentVaultId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const router = useRouter()
const authStore = useAuthStore()
const vaultStore = useVaultStore()

const newVaultNumber = ref('')
const creating = ref(false)
const deleting = ref<string | null>(null)

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const sortedVaults = computed(() =>
  [...vaultStore.vaults].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
)

const createVault = async () => {
  if (!newVaultNumber.value) return

  creating.value = true
  try {
    const number = parseInt(newVaultNumber.value)
    await vaultStore.createVault(number, authStore.token as string)
    await vaultStore.fetchVaults(authStore.token as string)

    // Get the newly created vault
    const newVault = vaultStore.vaults.find(v => v.number === number)
    if (newVault) {
      await router.push(`/vault/${newVault.id}`)
      isOpen.value = false
    }

    newVaultNumber.value = ''
  } finally {
    creating.value = false
  }
}

const selectVault = async (vaultId: string) => {
  localStorage.setItem('selectedVaultId', vaultId)
  await router.push(`/vault/${vaultId}`)
  isOpen.value = false
}

const deleteVault = async (vaultId: string) => {
  if (!confirm('Are you sure you want to delete this vault? This action cannot be undone.')) {
    return
  }

  deleting.value = vaultId
  try {
    await vaultStore.deleteVault(vaultId, authStore.token as string)
    await vaultStore.fetchVaults(authStore.token as string)

    // If deleted current vault, redirect to first available or home
    if (vaultId === props.currentVaultId) {
      if (vaultStore.vaults.length > 0) {
        const firstVault = vaultStore.vaults[0]
        if (firstVault) {
          localStorage.setItem('selectedVaultId', firstVault.id)
          await router.push(`/vault/${firstVault.id}`)
        }
      } else {
        await router.push('/')
      }
    }
  } finally {
    deleting.value = null
  }
}
</script>

<template>
  <UModal
    v-model="isOpen"
    :ui="{
      background: 'bg-black/95',
      ring: 'ring-2 ring-primary-600',
      width: 'max-w-4xl'
    }"
  >
    <UCard
      :ui="{
        base: 'border-2 border-primary-600 bg-black',
        header: { background: 'bg-black' },
        body: { background: 'bg-black' }
      }"
    >
      <template #header>
        <h2 class="text-2xl font-bold text-primary-500 uppercase tracking-wider text-center">
          VAULT-TEC VAULT MANAGEMENT SYSTEM
        </h2>
      </template>

      <!-- Create New Vault -->
      <div class="mb-8 p-6 border-2 border-primary-600 bg-black">
        <h3 class="text-xl font-bold text-primary-500 uppercase mb-4">CONSTRUCT NEW VAULT</h3>
        <form @submit.prevent="createVault" class="flex space-x-4">
          <UInput
            v-model="newVaultNumber"
            type="number"
            placeholder="VAULT NUMBER (1-999)"
            size="lg"
            color="primary"
            variant="outline"
            class="flex-1 font-mono"
            :ui="{ base: 'bg-black border-primary-600 text-primary-500 uppercase' }"
            :disabled="creating"
          />
          <UButton
            type="submit"
            size="lg"
            color="primary"
            :loading="creating"
            :disabled="creating || !newVaultNumber"
            class="uppercase font-bold"
          >
            {{ creating ? 'CONSTRUCTING...' : 'CONSTRUCT' }}
          </UButton>
        </form>
      </div>

      <!-- Vault List -->
      <div v-if="sortedVaults.length">
        <h3 class="text-xl font-bold text-primary-500 uppercase mb-4">EXISTING VAULTS</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-96 overflow-y-auto">
          <UCard
            v-for="vault in sortedVaults"
            :key="vault.id"
            :ui="{
              base: 'border-2 border-primary-600 bg-black cursor-pointer transition-all hover:border-primary-500',
              body: { base: 'space-y-2' }
            }"
            :class="{ 'ring-2 ring-primary-500': vault.id === currentVaultId }"
            @click="selectVault(vault.id)"
          >
            <div class="flex items-start justify-between mb-3">
              <div>
                <h4 class="text-lg font-bold text-primary-500">VAULT {{ vault.number }}</h4>
                <p class="text-xs text-primary-700 uppercase">
                  {{ new Date(vault.updated_at).toLocaleDateString() }}
                </p>
              </div>
              <UBadge
                v-if="vault.id === currentVaultId"
                color="primary"
                variant="solid"
              >
                ACTIVE
              </UBadge>
            </div>

            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="text-primary-700 uppercase">Caps:</div>
              <div class="text-primary-500 font-bold">{{ vault.bottle_caps }}</div>

              <div class="text-primary-700 uppercase">Happiness:</div>
              <div class="text-primary-500 font-bold">{{ vault.happiness }}%</div>

              <div class="text-primary-700 uppercase">Dwellers:</div>
              <div class="text-primary-500 font-bold">{{ vault.dweller_count }}</div>

              <div class="text-primary-700 uppercase">Rooms:</div>
              <div class="text-primary-500 font-bold">{{ vault.room_count }}</div>
            </div>

            <div class="flex space-x-2 mt-4 pt-4 border-t border-primary-800">
              <UButton
                v-if="vault.id !== currentVaultId"
                size="sm"
                color="primary"
                variant="solid"
                class="flex-1 uppercase"
                @click.stop="selectVault(vault.id)"
              >
                LOAD VAULT
              </UButton>
              <UButton
                size="sm"
                color="red"
                variant="outline"
                :loading="deleting === vault.id"
                :disabled="deleting === vault.id"
                class="uppercase"
                @click.stop="deleteVault(vault.id)"
              >
                DELETE
              </UButton>
            </div>
          </UCard>
        </div>
      </div>

      <!-- No Vaults Message -->
      <div v-else class="text-center py-12">
        <p class="text-xl text-primary-700 uppercase">NO VAULTS CONSTRUCTED</p>
        <p class="text-sm text-primary-900 mt-2">Create your first vault to begin</p>
      </div>
    </UCard>
  </UModal>
</template>
