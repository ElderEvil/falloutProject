import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory, useRoute, useRouter } from 'vue-router'
import { defineComponent, h, ref, watch } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import MarkerDetailModal from '@/modules/map/components/MarkerDetailModal.vue'
import type { WastelandLocationWithDwellers } from '@/modules/map/models/map'

// Regression guard: clicking a linked dweller must reach the dweller route. The
// modal closes and navigates, but MapView's `?place=` cleanup (a router.replace on
// close) used to run in the same tick and cancel the push, stranding the user on
// the map. The harness mirrors that cleanup so the interaction is covered without
// mounting the whole MapView.

const location: WastelandLocationWithDwellers = {
  id: 'loc-1',
  name: 'The Boneyard',
  normalized_name: 'the boneyard',
  type: 'origin',
  coord_x: 1,
  coord_y: 2,
  description: 'x',
  vault_id: 'v1',
  exploration_id: null,
  created_at: null,
  dwellers: [
    {
      dweller_id: 'd1',
      first_name: 'Adam',
      last_name: 'Morrison',
      relation: 'visited',
      is_unlocked: true,
    },
  ],
  is_unlocked: true,
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/vault/:id/map', name: 'map', component: { template: '<div />' } },
      {
        path: '/vault/:id/dwellers/:dwellerId',
        name: 'dwellerDetail',
        component: { template: '<div />' },
      },
    ],
  })
}

const Parent = defineComponent({
  setup() {
    const route = useRoute()
    const router = useRouter()
    const showModal = ref(true)
    watch(showModal, (open) => {
      if (open) return
      if (route.query.place === undefined) return
      const query = { ...route.query }
      delete query.place
      void router.replace({ query })
    })
    return () =>
      h(MarkerDetailModal, {
        modelValue: showModal.value,
        'onUpdate:modelValue': (v: boolean) => {
          showModal.value = v
        },
        location,
        vaultMarker: null,
      })
  },
})

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 20))
}

describe('map modal -> dweller navigation', () => {
  it('reaches the dweller route after clicking a linked dweller', async () => {
    setActivePinia(createPinia())
    const router = makeRouter()
    await router.push('/vault/v1/map?place=loc-1')
    await router.isReady()

    const wrapper = mount(Parent, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    const modal = wrapper.findComponent(MarkerDetailModal)
    ;(modal.vm as unknown as { goToDweller: (id: string) => void }).goToDweller('d1')

    await settle()

    expect(router.currentRoute.value.path).toBe('/vault/v1/dwellers/d1')
  })

  it('drops ?place= and opens chat when a locked-location contact is clicked', async () => {
    setActivePinia(createPinia())
    const router = makeRouter()
    await router.push('/vault/v1/map?place=loc-1')
    await router.isReady()

    const wrapper = mount(Parent, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    const modal = wrapper.findComponent(MarkerDetailModal)
    ;(modal.vm as unknown as { goToDwellerChat: (id: string) => void }).goToDwellerChat('d1')

    await settle()

    expect(router.currentRoute.value.path).toBe('/vault/v1/map')
    expect(router.currentRoute.value.query).toEqual({ chat: 'd1' })
  })
})
