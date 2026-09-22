import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerCard from '@/modules/dwellers/components/cards/DwellerCard.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'

// Mock the happiness service
vi.mock('@/modules/dwellers/services/happinessService', () => ({
  happinessService: {
    getDwellerModifiers: vi.fn().mockResolvedValue({
      data: { positive: [], negative: [] },
    }),
  },
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('DwellerCard', () => {
  const mockDweller = {
    id: '123',
    first_name: 'John',
    last_name: 'Doe',
    level: 5,
    health: 80,
    max_health: 100,
    happiness: 75,
    strength: 8,
    perception: 6,
    endurance: 7,
    charisma: 5,
    intelligence: 4,
    agility: 6,
    luck: 7,
    gender: 'male',
    rarity: 'common',
    experience: 450,
    radiation: 0,
    stimpack: 2,
    radaway: 1,
    status: 'idle',
    is_adult: true,
    age_group: 'adult',
    room: null,
  } as any

  describe('Portrait Display', () => {
    it('should render portrait placeholder when no image', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const placeholder = wrapper.find('.portrait-placeholder')
      expect(placeholder.exists()).toBe(true)
    })

    it('makes the empty portrait a direct generate action', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const placeholder = wrapper.find('.portrait-placeholder')
      expect(placeholder.text()).toContain('Generate portrait')

      await placeholder.trigger('click')
      expect(wrapper.emitted('generate-portrait')).toHaveLength(1)
    })

    it('should render portrait image when imageUrl is provided', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: 'https://example.com/image.jpg',
        },
      })

      const image = wrapper.find('.portrait-image')
      expect(image.exists()).toBe(true)
      expect(image.attributes('src')).toContain('example.com/image.jpg')
    })

    it('uses the API origin for backend static portraits', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: '/static/legendary_dweller_images/FOS_Dw_Butch.png',
        },
      })

      expect(wrapper.find('.portrait-image').attributes('src')).toBe(
        'http://localhost:8000/static/legendary_dweller_images/FOS_Dw_Butch.png'
      )
    })

    it('marks a dead dweller portrait as deceased', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, is_dead: true },
          imageUrl: 'https://example.com/image.jpg',
        },
      })

      expect(wrapper.find('.portrait-image').classes()).toContain('grayscale')
      expect(wrapper.find('.dead-portrait-marker').exists()).toBe(true)
    })
  })

  describe('Stats Display', () => {
    it('should display level', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Level')
      expect(wrapper.text()).toContain('5')
    })

    it('should display health', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Health')
      expect(wrapper.text()).toContain('80 / 100')
    })

    it('shows radiation-reduced maximum health', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, health: 82, max_health: 120, radiation: 35 },
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('82 / 85 (120)')
    })

    it('should display happiness percentage', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Happiness')
      expect(wrapper.text()).toContain('75%')
    })

    it('should display health bar', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const progressBar = wrapper.findComponent({ name: 'HealthRadiationBar' })
      expect(progressBar.exists()).toBe(true)
      expect(progressBar.props('value')).toBe(80)
    })

    it('describes the maximum level instead of a negative XP remainder', () => {
      const maxedDweller = { ...mockDweller, level: 50, experience: 50000 }
      // Reka renders TooltipContent only when open and teleported; stub it inline so the
      // max-level description (the behavioral contract) is assertable without hover timers.
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: maxedDweller,
          imageUrl: null,
        },
        global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } },
      })

      const value = wrapper.find('.xp-bar-container .stat-value')
      expect(value.classes()).toContain('max-level')
      expect(value.text()).not.toMatch(/-\d/)
      expect(wrapper.text()).toContain('Maximum level reached')
    })
  })

  describe('App HUD', () => {
    it('reads progress as one level-first block, not a level row plus an XP row', () => {
      const wrapper = mount(DwellerCard, { props: { dweller: mockDweller, imageUrl: null } })

      expect(wrapper.text()).toContain('Level 5')
      expect(wrapper.find('.xp-bar-container .stat-value').text()).toBe('1019 XP to L6')
    })
  })

  describe('Away and dead dwellers', () => {
    const actionLabels = (wrapper: ReturnType<typeof mount>) =>
      wrapper
        .findAllComponents({ name: 'Button' })
        .map((btn) => btn.text().trim())
        .filter(Boolean)

    it('replaces the room actions with Recall while exploring', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, status: 'exploring', room: null },
          imageUrl: null,
        },
      })

      const labels = actionLabels(wrapper)
      expect(labels).toContain('Recall')
      expect(wrapper.find('.actions-container').element.children).toHaveLength(2)
      expect(labels).not.toContain('Assign')
      expect(labels).not.toContain('Wasteland')
      expect(labels).not.toContain('Train')
    })

    it('swaps Recall for a Returning state once the dweller is heading home', () => {
      const explorationStore = useExplorationStore()
      explorationStore.explorations = [
        { id: 'e1', dweller_id: mockDweller.id, vault_id: 'v1', status: 'returning' },
      ] as any

      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, status: 'exploring', room: null },
          imageUrl: null,
        },
      })

      const labels = actionLabels(wrapper)
      expect(labels).toContain('Returning')
      expect(labels).not.toContain('Recall')
    })

    it('withholds vault actions from a questing dweller', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, status: 'questing', room: null },
          imageUrl: null,
        },
      })

      const labels = actionLabels(wrapper)
      expect(labels).toContain('Chat')
      expect(wrapper.find('.actions-container').element.children).toHaveLength(1)
      expect(labels).not.toContain('Assign')
      expect(labels).not.toContain('Wasteland')
      expect(labels).not.toContain('Train')
    })

    it('offers no vault actions for a dead dweller', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, is_dead: true, room: null },
          imageUrl: null,
        },
      })

      const labels = actionLabels(wrapper)
      expect(labels).not.toContain('Assign')
      expect(labels).not.toContain('Wasteland')
      expect(labels).not.toContain('Train')
    })

    it('does not offer Unassign for a dead dweller that still has a room', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, is_dead: true, room: { id: 'r1', name: 'Diner' } },
          imageUrl: null,
        },
      })

      expect(actionLabels(wrapper)).not.toContain('Unassign')
    })
  })
  describe('Inventory Display', () => {
    it('lets the overseer issue one supply from the counter', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          availableStimpaks: 1,
        },
      })

      await wrapper.get('[aria-label="Issue Stimpack from vault"]').trigger('click')

      expect(wrapper.emitted('issue-medical-supply')).toEqual([['stimpack']])
    })

    it('waits for vault stock before enabling supply issue', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          availableStimpaks: 0,
        },
      })

      expect(wrapper.find('[aria-label="Issue Stimpack from vault"]').exists()).toBe(false)
    })

    it('should display stimpack count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Stimpack')
      expect(wrapper.text()).toContain('2')
    })

    it('should display radaway count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('RadAway')
      expect(wrapper.text()).toContain('1')
    })
  })

  describe('Action Buttons', () => {
    it('should emit chat event when chat button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const chatButton = wrapper.findAll('button').find((btn) => btn.text().includes('Chat'))

      expect(chatButton).toBeDefined()
      await chatButton!.trigger('click')
      expect(wrapper.emitted('chat')).toBeTruthy()
    })

    it('should emit assign event when assign button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const assignButton = wrapper.findAll('button').find((btn) => btn.text().includes('Assign'))

      expect(assignButton).toBeDefined()
      await assignButton!.trigger('click')
      expect(wrapper.emitted('assign')).toBeTruthy()
    })

    it('should show recall button when dweller is exploring', async () => {
      const exploringDweller = { ...mockDweller, status: 'exploring' }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: exploringDweller,
          imageUrl: null,
        },
      })

      const recallButton = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Recall'))

      expect(recallButton).toBeDefined()
    })

    it('should not show recall button when dweller is not exploring', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const recallButton = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Recall'))

      expect(recallButton).toBeUndefined()
    })

    it('disables send to wasteland for a child', () => {
      const childDweller = { ...mockDweller, is_adult: false, age_group: 'child' }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: childDweller,
          imageUrl: null,
        },
      })

      const sendButton = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Wasteland'))

      expect(sendButton).toBeDefined()
      expect(sendButton!.props('disabled')).toBe(true)
    })

    it('enables send to wasteland for an adult', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const sendButton = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Wasteland'))

      expect(sendButton!.props('disabled')).toBeFalsy()
    })
  })

  describe('Item Usage', () => {
    it('should enable stimpack use button when stimpack available and health not full', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const useStimpakBtn = wrapper.find('[aria-label="Use Stimpack"]')
      expect(useStimpakBtn.exists()).toBe(true)
      expect(useStimpakBtn.attributes('disabled')).toBeUndefined()
    })

    it('draws no supplies for a healthy dweller with empty pockets', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, health: 100, radiation: 0, stimpack: 0, radaway: 0 },
          imageUrl: null,
          availableStimpaks: 5,
          availableRadaways: 5,
        },
      })

      expect(wrapper.find('.supplies').exists()).toBe(false)
    })

    it('hides the stimpack row when the dweller neither carries nor needs one', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, stimpack: 0 },
          imageUrl: null,
        },
      })

      expect(wrapper.find('.supply-stimpack').exists()).toBe(false)
    })

    it('shows the stimpack row with an issue action when hurt and the vault has stock', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, stimpack: 0 },
          imageUrl: null,
          availableStimpaks: 3,
        },
      })

      expect(wrapper.find('.supply-stimpack').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Issue Stimpack from vault"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Use Stimpack"]').exists()).toBe(false)
    })

    it('offers Use only when the supply would actually do something', () => {
      // Carries a RadAway but has no radiation to clear, so no Use action.
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.find('.supply-radaway').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Use RadAway"]').exists()).toBe(false)
      expect(wrapper.find('[aria-label="Use Stimpack"]').exists()).toBe(true)
    })

    it('should enable radaway use button when radiation exists', () => {
      const dwellerWithRadiation = { ...mockDweller, radiation: 10 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerWithRadiation,
          imageUrl: null,
        },
      })

      const useRadAwayBtn = wrapper.find('[aria-label="Use RadAway"]')
      expect(useRadAwayBtn.exists()).toBe(true)
      expect(useRadAwayBtn.attributes('disabled')).toBeUndefined()
    })

    it('emits use-stimpak when the Use button is clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      await wrapper.find('[aria-label="Use Stimpack"]').trigger('click')
      expect(wrapper.emitted('use-stimpak')).toBeTruthy()
    })

    it('emits use-radaway when the Use button is clicked', async () => {
      const dwellerWithRadiation = { ...mockDweller, radiation: 10 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerWithRadiation,
          imageUrl: null,
        },
      })

      await wrapper.find('[aria-label="Use RadAway"]').trigger('click')
      expect(wrapper.emitted('use-radaway')).toBeTruthy()
    })
  })

  describe('Contextual Room Actions', () => {
    const actionLabels = (wrapper: ReturnType<typeof mount>) =>
      wrapper
        .findAllComponents({ name: 'Button' })
        .map((btn) => btn.text().trim())
        .filter(Boolean)

    it('offers Assign and not Unassign when the dweller has no room', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(actionLabels(wrapper)).toContain('Assign')
      expect(actionLabels(wrapper)).not.toContain('Unassign')
    })

    it('offers Unassign and not Assign when the dweller has a room', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, room: { id: 'r1', name: 'Diner' } },
          imageUrl: null,
        },
      })

      expect(actionLabels(wrapper)).toContain('Unassign')
      expect(actionLabels(wrapper)).not.toContain('Assign')
    })

    it('labels the assign action as an apprenticeship for youth', () => {
      const childDweller = { ...mockDweller, is_adult: false, age_group: 'child' }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: childDweller,
          imageUrl: null,
        },
      })

      expect(actionLabels(wrapper)).toContain('Apprentice')
      expect(actionLabels(wrapper)).not.toContain('Assign')
    })
  })

  describe('Button Tooltips', () => {
    it('should have tooltip for train stats button', () => {
      // Reka renders TooltipContent only when open and teleported; stub it inline so the
      // tooltip text (the behavioral contract) is assertable without hover timers.
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
        global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } },
      })

      expect(wrapper.text()).toContain('Train SPECIAL stats to improve dweller abilities')
    })
  })
})
