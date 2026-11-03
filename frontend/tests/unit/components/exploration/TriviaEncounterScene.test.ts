import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import TriviaEncounterScene from '@/modules/exploration/components/TriviaEncounterScene.vue'
import type { SiteRoomView } from '@/modules/exploration/api/expeditionSite'

const triviaRoom: SiteRoomView = {
  exploration_id: 'exp-trivia',
  site_id: 'red_rocket',
  site_name: 'Red Rocket',
  room_index: 0,
  room_total: 1,
  room_name: 'Raider Tollbooth',
  flavor: 'A raider leans on a wrecked car.',
  scene_id: 'desert_highway',
  node: {
    kind: 'trivia',
    prompt: 'The raider taps her rifle.',
    question: 'Which pre-war company built the Vaults?',
    question_index: 1,
    question_total: 3,
    raider_image_url: '/static/raider_images/variants/jinx.webp',
    raider_alt_image_url: '/static/raider_images/variants/jinx_alt.webp',
    options: [
      { id: 'vault-tec', label: 'Vault-Tec' },
      { id: 'robco', label: 'RobCo Industries' },
    ],
    enemy_names: ['Raider'],
  },
  can_retreat: true,
  status: 'in_room',
  outcome: null,
  finale_paid: false,
  defeated: false,
  dweller_health: 50,
  dweller_max_health: 60,
}

const mountScene = (overrides: Partial<SiteRoomView> = {}, busy = false) =>
  mount(TriviaEncounterScene, {
    props: { room: { ...triviaRoom, ...overrides }, dwellerName: 'Lucy', busy },
  })

describe('TriviaEncounterScene', () => {
  it('renders the scene artwork and the raider inside it', () => {
    const wrapper = mountScene()

    const scene = wrapper.get('img[alt="Desert highway"]')
    expect(scene.attributes('srcset')).toContain('1280w')
    expect(scene.attributes('width')).toBe('1280')
    expect(scene.attributes('height')).toBe('720')

    const raider = wrapper.get('img[alt="Raider posing the question"]')
    expect(raider.attributes('src')).toContain('/static/raider_images/variants/jinx')
    expect(wrapper.get('[aria-label="Raider posing a question"]').exists()).toBe(true)
  })

  it('shows the question, progress and plain answer labels', () => {
    const wrapper = mountScene()

    expect(wrapper.get('[aria-live="polite"]').text()).toBe(
      'Which pre-war company built the Vaults?'
    )
    expect(wrapper.get('[aria-label="Question 1 of 3"]').text()).toBe('QUESTION 1 / 3')
    expect(wrapper.text()).toContain('If it goes wrong: Raider')
    expect(wrapper.text()).toContain('The raider taps her rifle.')

    const answers = wrapper.findAll('button[type="button"]')
    expect(answers).toHaveLength(2)
    expect(answers.map((button) => button.text())).toEqual(['Vault-Tec', 'RobCo Industries'])
    for (const answer of answers) expect(answer.text()).not.toContain('%')
  })

  it('emits the chosen option id', async () => {
    const wrapper = mountScene()

    await wrapper.findAll('button[type="button"]')[1]!.trigger('click')

    expect(wrapper.emitted('answer')).toEqual([['robco']])
  })

  it('disables the answer buttons while busy', () => {
    const wrapper = mountScene({}, true)

    for (const answer of wrapper.findAll('button[type="button"]')) {
      expect(answer.attributes('disabled')).toBeDefined()
    }
    expect(wrapper.text()).toContain('Checking your answer')
  })

  it('floats the in-room outcome above the question', () => {
    const wrapper = mountScene({
      outcome: {
        text: 'Correct answer — the raider waves you through. Next question.',
        damage_taken: 0,
        caps_gained: 0,
        loot_gained: [],
      },
    })

    expect(wrapper.text()).toContain('Correct answer — the raider waves you through.')
  })
})
