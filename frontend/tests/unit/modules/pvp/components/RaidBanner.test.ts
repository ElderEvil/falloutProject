import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import RaidBanner from '@/modules/pvp/components/RaidBanner.vue'
import { usePvpStore } from '@/modules/pvp/stores/pvp'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import type { PvpBoardEntry, PvpDuel } from '@/modules/pvp/services/pvpDuelService'
import type { DefineComponent } from 'vue'

const boardEntry = (duelId: string) =>
  ({
    duel_id: duelId,
    challenger_vault_name: `Vault ${duelId}`,
    party_size: 2,
    member_names: ['Ana', 'Bo'],
    power_band: 'mid',
    expires_at: new Date().toISOString(),
  }) as unknown as PvpBoardEntry

const ownDuel = (status: 'OPEN' | 'ACCEPTED') =>
  ({
    duel_id: 'own-duel',
    status,
    challenger_vault_id: 'vault-1',
    expires_at: new Date().toISOString(),
  }) as unknown as PvpDuel

async function mountBanner() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/vault/:id/pvp', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()

  const wrapper = mount(RaidBanner as DefineComponent, {
    props: { vaultId: 'vault-1' },
    global: {
      plugins: [router],
      stubs: { Icon: true },
    },
  })
  await flushPromises()

  return wrapper
}

describe('RaidBanner', () => {
  let store: ReturnType<typeof usePvpStore>
  let flags: ReturnType<typeof useFeatureFlagsStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePvpStore()
    flags = useFeatureFlagsStore()
    flags.pvpDuels = true
    // The banner only advertises state; the load itself is covered elsewhere.
    vi.spyOn(store, 'load').mockResolvedValue(true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('offers the raid board even when no challenge is waiting', async () => {
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()
    const link = wrapper.find('a')

    // An empty board still needs a door, or nobody can post the first challenge.
    expect(link.text()).toContain('RAID BOARD · POST A CHALLENGE')
    expect(link.attributes('href')).toBe('/vault/vault-1/pvp')
  })

  it('loads the duel board for its own vault, silently', async () => {
    await mountBanner()

    expect(store.load).toHaveBeenCalledWith('vault-1', undefined, { silent: true })
  })

  it('does nothing at all while the duels flag is off', async () => {
    flags.pvpDuels = false
    store.board = [boardEntry('duel-1')]
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()

    // A banner would advertise a surface whose endpoints 404, and the load would toast the player.
    expect(wrapper.find('a').exists()).toBe(false)
    expect(store.load).not.toHaveBeenCalled()
  })

  it('starts advertising once the flag arrives after mount', async () => {
    flags.pvpDuels = false
    const wrapper = await mountBanner()
    expect(store.load).not.toHaveBeenCalled()

    store.board = [boardEntry('duel-1')]
    store.stateVaultId = 'vault-1'
    flags.pvpDuels = true
    await flushPromises()

    expect(store.load).toHaveBeenCalledWith('vault-1', undefined, { silent: true })
    expect(wrapper.find('a').text()).toContain('1 CHALLENGE AWAITS A DEFENDER')
  })

  it('never shows another vault challenge', async () => {
    // The store keeps the last loaded vault's board; this banner is for vault-1.
    store.board = [boardEntry('duel-from-vault-2')]
    store.stateVaultId = 'vault-2'

    const wrapper = await mountBanner()

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('advertises a single waiting challenge and links to the arena route', async () => {
    store.board = [boardEntry('duel-1')]
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()
    const link = wrapper.find('a')

    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('1 CHALLENGE AWAITS A DEFENDER')
    expect(link.attributes('href')).toBe('/vault/vault-1/pvp')
  })

  it('pluralises the copy for several waiting challenges', async () => {
    store.board = [boardEntry('duel-1'), boardEntry('duel-2'), boardEntry('duel-3')]
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()

    expect(wrapper.find('a').text()).toContain('3 CHALLENGES AWAIT A DEFENDER')
  })

  it('advertises the vault own open challenge', async () => {
    store.ownOpenDuel = ownDuel('OPEN')
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()

    expect(wrapper.find('a').text()).toContain('YOUR CHALLENGE AWAITS A DEFENDER')
    expect(wrapper.find('a').attributes('href')).toBe('/vault/vault-1/pvp')
  })

  it('prefers the defence invitation over the vault own open challenge', async () => {
    store.board = [boardEntry('duel-1')]
    store.ownOpenDuel = ownDuel('OPEN')
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()

    expect(wrapper.find('a').text()).toContain('1 CHALLENGE AWAITS A DEFENDER')
    expect(wrapper.text()).not.toContain('YOUR CHALLENGE')
  })

  it('falls back to the raid-board entry once the vault own challenge settles', async () => {
    store.ownOpenDuel = ownDuel('ACCEPTED')
    store.stateVaultId = 'vault-1'

    const wrapper = await mountBanner()

    expect(wrapper.find('a').text()).toContain('RAID BOARD · POST A CHALLENGE')
  })
})
