import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaActorStage, { type StageActor } from '@/modules/rooms/components/ArenaActorStage.vue'
import { ARENA_SCENE_POC, anchorToPercent } from '@/modules/rooms/models/arenaScenePoc'

// jsdom never evaluates media queries, so the reduced-motion contract is guarded
// at the source level — it is the only way to keep this a11y rule from silently rotting.
import stageSource from '@/modules/rooms/components/ArenaActorStage.vue?raw'

const actor = (overrides: Partial<StageActor> = {}): StageActor => ({
  id: 'd1',
  name: 'Alice',
  portraitUrl: null,
  outfitUrl: null,
  weaponUrl: null,
  ...overrides,
})

const mountStage = (props: Record<string, unknown> = {}) =>
  mount(ArenaActorStage, {
    props: { sceneUrl: null, actors: [], ...props },
  })

describe('ArenaActorStage', () => {
  it('renders the scene stage at the PoC intrinsic aspect ratio', () => {
    const wrapper = mountStage({ sceneUrl: 'https://cdn.test/arena.png' })
    const stage = wrapper.find('.arena-actor-stage')

    expect(stage.exists()).toBe(true)
    expect(stage.attributes('style')).toContain(
      `${ARENA_SCENE_POC.intrinsicWidth} / ${ARENA_SCENE_POC.intrinsicHeight}`
    )
    expect(wrapper.find('.stage-scene').attributes('src')).toBe('https://cdn.test/arena.png')
  })

  it('falls back to the grid art when no detail scene URL is provided', () => {
    const wrapper = mountStage({ sceneFallbackUrl: 'https://cdn.test/grid.png' })

    expect(wrapper.find('.stage-scene').attributes('src')).toBe('https://cdn.test/grid.png')
  })

  it('shows the placeholder treatment when no scene image is available', () => {
    const wrapper = mountStage()

    expect(wrapper.find('.stage-scene').exists()).toBe(false)
    expect(wrapper.find('.stage-placeholder').exists()).toBe(true)
    expect(wrapper.text()).toContain('No Image Available')
  })

  it('renders two actor wrappers from the PoC descriptor', () => {
    const wrapper = mountStage({
      actors: [actor({ id: 'd1' }), actor({ id: 'd2' })],
    })

    const wrappers = wrapper.findAll('.actor-wrapper')
    expect(wrappers).toHaveLength(2)
    expect(wrappers[0].attributes('style')).toContain(anchorToPercent(ARENA_SCENE_POC.anchors[0]).left)
    expect(wrappers[0].attributes('style')).toContain(anchorToPercent(ARENA_SCENE_POC.anchors[0]).top)
    expect(wrappers[1].attributes('style')).toContain(anchorToPercent(ARENA_SCENE_POC.anchors[1]).left)
  })

  it('sizes actors as a percentage of the stage width, not a fixed box', () => {
    const wrapper = mountStage({ actors: [actor({ id: 'd1' })] })

    const actorWrapper = wrapper.find('.actor-wrapper')
    expect(actorWrapper.attributes('style')).toContain(`${ARENA_SCENE_POC.actorWidthPercent}%`)
    expect(actorWrapper.attributes('style')).not.toContain('96px')
  })

  it('renders equipment layer images when outfit and weapon URLs are provided', () => {
    const wrapper = mountStage({
      actors: [
        actor({
          portraitUrl: 'https://cdn.test/base.png',
          outfitUrl: 'https://cdn.test/outfit.png',
          weaponUrl: 'https://cdn.test/weapon.png',
        }),
      ],
    })

    expect(wrapper.find('.actor-layer--base').attributes('src')).toBe('https://cdn.test/base.png')
    expect(wrapper.find('.actor-layer--outfit').attributes('src')).toBe('https://cdn.test/outfit.png')
    expect(wrapper.find('.actor-layer--weapon').attributes('src')).toBe('https://cdn.test/weapon.png')
  })

  it('swaps equipment layer images when the actor props change', async () => {
    const wrapper = mountStage({
      actors: [
        actor({
          portraitUrl: 'https://cdn.test/base.png',
          outfitUrl: 'https://cdn.test/outfit-a.png',
          weaponUrl: 'https://cdn.test/weapon-a.png',
        }),
      ],
    })

    await wrapper.setProps({
      actors: [
        actor({
          portraitUrl: 'https://cdn.test/base.png',
          outfitUrl: 'https://cdn.test/outfit-b.png',
          weaponUrl: 'https://cdn.test/weapon-b.png',
        }),
      ],
    })

    expect(wrapper.find('.actor-layer--outfit').attributes('src')).toBe('https://cdn.test/outfit-b.png')
    expect(wrapper.find('.actor-layer--weapon').attributes('src')).toBe('https://cdn.test/weapon-b.png')
  })

  it('renders a visible no-portrait fallback with no equipment layers when the base portrait is missing', () => {
    const wrapper = mountStage({
      actors: [
        actor({
          portraitUrl: null,
          outfitUrl: 'https://cdn.test/outfit.png',
          weaponUrl: 'https://cdn.test/weapon.png',
        }),
      ],
    })

    const fallback = wrapper.find('.actor-no-portrait')
    expect(fallback.exists()).toBe(true)
    expect(fallback.attributes('aria-label')).toBe('Alice')
    expect(wrapper.find('.actor-layer--base').exists()).toBe(false)
    expect(wrapper.find('.actor-layer--outfit').exists()).toBe(false)
    expect(wrapper.find('.actor-layer--weapon').exists()).toBe(false)
  })

  it('shows a missing-actor cue for empty slots', () => {
    const wrapper = mountStage({ actors: [actor({ id: 'd1' })] })

    expect(wrapper.findAll('.actor-wrapper')).toHaveLength(2)
    expect(wrapper.findAll('.actor-missing')).toHaveLength(1)
  })

  it('applies the idle animation class to actor wrappers', () => {
    const wrapper = mountStage({ actors: [actor({ id: 'd1' })] })

    expect(wrapper.find('.actor-idle').exists()).toBe(true)
  })

  it('stops the idle animation under prefers-reduced-motion', () => {
    expect(stageSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.actor-idle \{\s*animation: none;/
    )
  })
})
