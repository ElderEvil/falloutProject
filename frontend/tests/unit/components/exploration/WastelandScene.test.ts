import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import WastelandScene from '@/modules/exploration/components/WastelandScene.vue'
import {
  getLocationScene,
  getSiteScene,
  WASTELAND_SCENES,
} from '@/modules/exploration/models/wastelandScenes'

const props = {
  scene: 'desert_highway' as const,
  heading: "Lucy's wasteland journey",
  dwellerName: 'Lucy',
}

describe('Wasteland scenes', () => {
  it('offers responsive images with reserved dimensions and an accessible caption', () => {
    const wrapper = mount(WastelandScene, { props })
    const image = wrapper.get('img')
    expect(image.attributes('width')).toBe('1280')
    expect(image.attributes('height')).toBe('720')
    expect(image.attributes('srcset')).toContain('640w')
    expect(image.attributes('srcset')).toContain('1280w')
    expect(wrapper.get('figcaption').text()).toContain("Lucy's wasteland journey")
    expect(wrapper.get('[role="group"]').attributes('aria-label')).toBe('Lucy on expedition')
  })

  it('uses the supplied battleback framing for encounters', () => {
    const wrapper = mount(WastelandScene, {
      props: { ...props, scene: 'supermarket_interior', variant: 'battleback' },
    })
    expect(wrapper.get('img').attributes()).toMatchObject({
      width: '1000',
      height: '740',
      alt: 'Abandoned supermarket',
    })
    expect(wrapper.get('img').attributes('src')).toContain('-battleback-')
  })

  it('keeps the scene and explorer readable when artwork fails, and retries a changed scene', async () => {
    const wrapper = mount(WastelandScene, { props })
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('figure').exists()).toBe(true)
    expect(wrapper.get('[role="img"]').attributes('aria-label')).toBe('Desert highway')
    expect(wrapper.get('figcaption').text()).toContain('Lucy')
    await wrapper.setProps({ scene: 'subway_station' })
    expect(wrapper.get('img').attributes('alt')).toBe('Subway station')
  })

  it.each([
    ['Super Duper Mart', 'supermarket_interior'],
    ['SUPER-DUPER MART', 'supermarket_interior'],
    ['Metro Central', 'subway_station'],
    ['Nuka-World', 'amusement_park'],
    ['Arctic research station', 'arctic_research_station'],
    ['Roadside supply truck', 'desert_highway'],
    ['Research laboratory', null],
    ['Cinema', null],
    ['', null],
  ])('matches reported location %s without inventing scenery', (name, expected) => {
    expect(getLocationScene(name)).toBe(expected)
  })

  it('distinguishes supermarket interiors from its outdoor parking-lot encounter', () => {
    expect(getSiteScene('super_duper_mart', 'Collapsed Aisles')).toBe('supermarket_interior')
    expect(getSiteScene('super_duper_mart', 'Parking Lot')).toBe('desert_highway')
    expect(getSiteScene('roadside_supply_truck')).toBe('desert_highway')
    expect(getSiteScene('red_rocket', 'Garage')).toBeNull()
  })

  it('ships every responsive variant as a content-addressed WebP within its asset budget', () => {
    for (const scene of Object.values(WASTELAND_SCENES)) {
      for (const role of ['landscape', 'battleback'] as const) {
        for (const variant of scene[role].variants) {
          const bytes = readFileSync(`public${variant.src}`)
          const hash = createHash('sha256').update(bytes).digest('hex').slice(0, 16)
          expect(variant.src).toContain(`-${hash}.webp`)
          expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
          expect(bytes.length).toBeLessThan(200000)
        }
      }
    }
  })
})
