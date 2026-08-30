<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import DwellerCardSkeleton from '@/modules/dwellers/components/cards/DwellerCardSkeleton.vue'
import DwellerBioBadge from '@/modules/dwellers/components/DwellerBioBadge.vue'
import DwellerPlacesBadge from '@/modules/dwellers/components/DwellerPlacesBadge.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { tradingService } from '../services/tradingService'
import type { TradeOffer } from '../models/trading'

const props = defineProps<{ vaultId: string }>()

const authStore = useAuthStore()
const toast = useToast()

const marketOffers = ref<TradeOffer[]>([])
const myListings = ref<TradeOffer[]>([])
const bottleCaps = ref(0)
const isLoading = ref(false)
const busyDwellerId = ref<string | null>(null)

async function refreshMarket() {
  if (!authStore.token) return
  isLoading.value = true
  try {
    const market = await tradingService.getMarket(props.vaultId, authStore.token)
    marketOffers.value = market.market_offers
    myListings.value = market.my_listings
    bottleCaps.value = market.bottle_caps
  } catch (error) {
    toast.error(getErrorMessage(error, 'Failed to load the Trading Post'))
  } finally {
    isLoading.value = false
  }
}

async function sell(offer: TradeOffer) {
  if (!authStore.token) return
  busyDwellerId.value = offer.dweller.id
  try {
    const result = await tradingService.sellDweller(props.vaultId, offer.dweller.id, authStore.token)
    toast.success(`Sold for ${result.price} caps!`)
    await refreshMarket()
  } catch (error) {
    toast.error(getErrorMessage(error, 'Failed to sell dweller'))
  } finally {
    busyDwellerId.value = null
  }
}

async function buy(offer: TradeOffer) {
  if (!authStore.token) return
  busyDwellerId.value = offer.dweller.id
  try {
    const result = await tradingService.buyDweller(props.vaultId, offer.dweller.id, authStore.token)
    toast.success(`${offer.dweller.first_name} joined the vault for ${result.price} caps!`)
    await refreshMarket()
  } catch (error) {
    toast.error(getErrorMessage(error, 'Failed to buy dweller'))
  } finally {
    busyDwellerId.value = null
  }
}

onMounted(refreshMarket)
</script>

<template>
  <div class="trading-post">
    <div class="caps-bar">
      <Icon icon="mdi:currency-usd" class="h-5 w-5" />
      <span>{{ bottleCaps }} caps</span>
    </div>

    <div v-if="isLoading" class="space-y-4">
      <DwellerCardSkeleton v-for="i in 3" :key="`skeleton-${i}`" />
    </div>

    <template v-else>
      <section class="offer-section">
        <h3 class="section-title">Your Listings</h3>
        <p v-if="myListings.length === 0" class="state-message">Soft-delete a dweller to list them here.</p>
        <ul v-else class="space-y-4">
          <DwellerListRow v-for="offer in myListings" :key="offer.dweller.id" :dweller="offer.dweller" :clickable="false">
            <template #middle>
              <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>
              <div class="flex items-center gap-1.5">
                <DwellerBioBadge :has-bio="offer.has_bio" />
                <DwellerPlacesBadge :count="offer.places_visited" />
              </div>
            </template>
            <template #actions>
              <span class="text-sm font-bold text-terminal-green">{{ offer.price }} caps</span>
              <UButton
                variant="secondary"
                size="xs"
                :loading="busyDwellerId === offer.dweller.id"
                @click="sell(offer)"
              >
                Sell
              </UButton>
            </template>
          </DwellerListRow>
        </ul>
      </section>

      <section class="offer-section">
        <h3 class="section-title">Market</h3>
        <p v-if="marketOffers.length === 0" class="state-message">No dwellers on the market right now.</p>
        <ul v-else class="space-y-4">
          <DwellerListRow v-for="offer in marketOffers" :key="offer.dweller.id" :dweller="offer.dweller" :clickable="false">
            <template #middle>
              <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>
              <div class="flex items-center gap-1.5">
                <DwellerBioBadge :has-bio="offer.has_bio" />
                <DwellerPlacesBadge :count="offer.places_visited" />
              </div>
            </template>
            <template #actions>
              <span class="text-sm font-bold text-terminal-green">{{ offer.price }} caps</span>
              <UButton
                variant="primary"
                size="xs"
                :disabled="offer.price > bottleCaps"
                :loading="busyDwellerId === offer.dweller.id"
                @click="buy(offer)"
              >
                Buy
              </UButton>
            </template>
          </DwellerListRow>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.trading-post {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.caps-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-theme-primary);
  font-weight: bold;
}

.offer-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.state-message {
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-size: 0.875rem;
}
</style>
