import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaActorSprite from '@/modules/rooms/components/ArenaActorSprite.vue'
import type { components } from '@/core/types/api.generated'

type ArenaActor = components['schemas']['ArenaActor']
type ArenaActorLayer = components['schemas']['ArenaActorLayer']

// jsdom never evaluates media queries, so the reduced-motion contract is guarded
// at the source level — it is the only way to keep this a11y rule from silently rotting.
import spriteSource from '@/modules/rooms/components/ArenaActorSprite.vue?raw'

const CANVAS_WIDTH = 1024
const CANVAS_HEIGHT = 1536

const percent = (value: number, total: number) => `${(value / total) * 100}%`

const layer = (overrides: Partial<ArenaActorLayer> = {}): ArenaActorLayer => ({
  slot: 'body',
  url: 'https://cdn.test/body.png',
  z: 10,
  anchor_x: 0,
  anchor_y: 0,
  width: CANVAS_WIDTH,
  height: CANVAS_HEIGHT,
  ...overrides,
})

const actor = (overrides: Partial<ArenaActor> = {}): ArenaActor => ({
  base_key: 'adult.vault_suit',
  variant_url: null,
  canvas_width: CANVAS_WIDTH,
  canvas_height: CANVAS_HEIGHT,
  baseline_y: CANVAS_HEIGHT,
  layers: [layer()],
  ...overrides,
})

const mountSprite = (props: Record<string, unknown> = {}) =>
  mount(ArenaActorSprite, {
    props: { actor: null, portraitUrl: null, alt: 'Alice', ...props },
  })

describe('ArenaActorSprite', () => {
  it('sizes the sprite box at the actor canvas aspect ratio', () => {
    const wrapper = mountSprite({ actor: actor() })

    expect(wrapper.find('.arena-actor-sprite').attributes('style')).toContain(
      `${CANVAS_WIDTH} / ${CANVAS_HEIGHT}`
    )
  })

  it('positions each layer by anchor and size converted to box percentages', () => {
    const wrapper = mountSprite({
      actor: actor({
        layers: [
          layer({ slot: 'body', anchor_x: 0, anchor_y: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT }),
          layer({
            slot: 'outfit',
            url: 'https://cdn.test/outfit.png',
            z: 20,
            anchor_x: 0,
            anchor_y: 256,
            width: CANVAS_WIDTH,
            height: 1024,
          }),
          layer({
            slot: 'weapon',
            url: 'https://cdn.test/weapon.png',
            z: 30,
            anchor_x: 205,
            anchor_y: 400,
            width: 614,
            height: 614,
          }),
        ],
      }),
    })

    const outfit = wrapper.find('.actor-layer[alt="Alice outfit"]')
    expect(outfit.attributes('style')).toContain(`left: ${percent(0, CANVAS_WIDTH)}`)
    expect(outfit.attributes('style')).toContain(`top: ${percent(256, CANVAS_HEIGHT)}`)
    expect(outfit.attributes('style')).toContain(`width: ${percent(CANVAS_WIDTH, CANVAS_WIDTH)}`)
    expect(outfit.attributes('style')).toContain(`height: ${percent(1024, CANVAS_HEIGHT)}`)

    const weapon = wrapper.find('.actor-layer[alt="Alice weapon"]')
    expect(weapon.attributes('style')).toContain(`left: ${percent(205, CANVAS_WIDTH)}`)
    expect(weapon.attributes('style')).toContain(`top: ${percent(400, CANVAS_HEIGHT)}`)
    expect(weapon.attributes('style')).toContain(`width: ${percent(614, CANVAS_WIDTH)}`)
    expect(weapon.attributes('style')).toContain(`height: ${percent(614, CANVAS_HEIGHT)}`)
  })

  it('orders layers by z in the DOM and via z-index', () => {
    const wrapper = mountSprite({
      actor: actor({
        layers: [
          layer({ slot: 'weapon', url: 'https://cdn.test/weapon.png', z: 30 }),
          layer({ slot: 'body' }),
          layer({ slot: 'outfit', url: 'https://cdn.test/outfit.png', z: 20 }),
        ],
      }),
    })

    const rendered = wrapper.findAll('.actor-layer')
    expect(rendered.map((img) => img.attributes('alt'))).toEqual([
      'Alice body',
      'Alice outfit',
      'Alice weapon',
    ])
    expect(rendered.map((img) => img.attributes('style'))).toEqual([
      expect.stringContaining('z-index: 10'),
      expect.stringContaining('z-index: 20'),
      expect.stringContaining('z-index: 30'),
    ])
  })

  it('renders the variant above the body layer and below outfit/weapon', () => {
    const wrapper = mountSprite({
      actor: actor({
        variant_url: 'https://cdn.test/variant.png',
        layers: [
          layer({ slot: 'body' }),
          layer({ slot: 'outfit', url: 'https://cdn.test/outfit.png', z: 20 }),
          layer({ slot: 'weapon', url: 'https://cdn.test/weapon.png', z: 30 }),
        ],
      }),
    })

    const variantImg = wrapper.find('.actor-layer--variant')
    expect(variantImg.exists()).toBe(true)
    expect(variantImg.attributes('src')).toBe('https://cdn.test/variant.png')
    expect(variantImg.attributes('style')).toContain('z-index: 11')

    const zIndexes = wrapper
      .findAll('.actor-layer')
      .map((img) => Number(img.attributes('style')?.match(/z-index: (\d+)/)?.[1]))
    expect(Math.min(...zIndexes)).toBe(10)
    expect(Math.max(...zIndexes)).toBe(30)
    expect(zIndexes).toContain(11)
  })

  it('resolves root-relative layer URLs against the API origin', () => {
    const wrapper = mountSprite({
      actor: actor({ layers: [layer({ url: '/static/actors/body.png' })] }),
    })

    expect(wrapper.find('.actor-layer').attributes('src')).toBe(
      'http://localhost:8000/static/actors/body.png'
    )
  })

  it('falls back to the dweller portrait when the actor is null', () => {
    const wrapper = mountSprite({ actor: null, portraitUrl: 'https://cdn.test/portrait.png' })

    expect(wrapper.find('.actor-layer').exists()).toBe(false)
    expect(wrapper.find('.portrait-image').attributes('src')).toBe(
      'https://cdn.test/portrait.png'
    )
  })

  it('falls back to the dweller portrait when the actor has no layers', () => {
    const wrapper = mountSprite({
      actor: actor({ layers: [], variant_url: 'https://cdn.test/variant.png' }),
      portraitUrl: 'https://cdn.test/portrait.png',
    })

    expect(wrapper.find('.actor-layer').exists()).toBe(false)
    expect(wrapper.find('.portrait-image').attributes('src')).toBe(
      'https://cdn.test/portrait.png'
    )
  })

  it('falls back to the dweller portrait when a layer image fails to load', async () => {
    const wrapper = mountSprite({
      actor: actor({
        layers: [
          layer({ slot: 'body' }),
          layer({ slot: 'outfit', url: 'https://cdn.test/outfit.png', z: 20 }),
        ],
      }),
      portraitUrl: 'https://cdn.test/portrait.png',
    })

    expect(wrapper.find('.actor-layer').exists()).toBe(true)

    await wrapper.find('.actor-layer').trigger('error')

    expect(wrapper.find('.actor-layer').exists()).toBe(false)
    expect(wrapper.find('.portrait-image').attributes('src')).toBe(
      'https://cdn.test/portrait.png'
    )
  })

  it('restores the sprite when the actor changes after a load error', async () => {
    const wrapper = mountSprite({ actor: actor(), portraitUrl: 'https://cdn.test/portrait.png' })

    await wrapper.find('.actor-layer').trigger('error')
    expect(wrapper.find('.arena-actor-sprite--fallback').exists()).toBe(true)

    await wrapper.setProps({ actor: actor({ base_key: 'adult.alt' }) })

    expect(wrapper.find('.actor-layer').exists()).toBe(true)
    expect(wrapper.find('.arena-actor-sprite--fallback').exists()).toBe(false)
  })

  it('shows the portrait icon fallback when no portrait is available either', () => {
    const wrapper = mountSprite({ actor: null, portraitUrl: null })

    expect(wrapper.find('.portrait-icon').exists()).toBe(true)
    const portrait = wrapper.find('span[role="img"]')
    expect(portrait.exists()).toBe(true)
    expect(portrait.attributes('aria-label')).toBe('Alice')
  })

  it('applies the idle animation class to the sprite', () => {
    const wrapper = mountSprite({ actor: actor() })

    expect(wrapper.find('.actor-idle').exists()).toBe(true)
  })

  it('stops the idle animation under prefers-reduced-motion', () => {
    expect(spriteSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.actor-idle \{\s*animation: none;/
    )
  })
})
