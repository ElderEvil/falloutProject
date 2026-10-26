import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import WastelandScene from '@/modules/exploration/components/WastelandScene.vue'
import { WASTELAND_SCENES, widestSceneImage } from '@/modules/exploration/models/wastelandScenes'

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

  it('reserves the encounter frame and actor for a site without authored artwork', () => {
    const wrapper = mount(WastelandScene, {
      props: { ...props, scene: null, variant: 'battleback' },
    })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('[role="img"]').attributes('aria-label')).toBe(props.heading)
    expect(wrapper.get('[role="group"]').exists()).toBe(true)
  })

  it('chooses the widest variant independent of manifest order and handles a single image', () => {
    const variants = WASTELAND_SCENES.desert_highway.landscape.variants
    expect(widestSceneImage([...variants].reverse())?.width).toBe(1280)
    expect(widestSceneImage([variants[0]!])?.width).toBe(640)
    expect(widestSceneImage([])).toBeUndefined()
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
