import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProfileEditor from '@/components/profile/ProfileEditor.vue'
import type { ProfileUpdate } from '@/models/profile'

describe('ProfileEditor', () => {
  const mockInitialData = {
    bio: 'Test bio',
    avatar_url: 'https://example.com/avatar.jpg',
    preferences: { theme: 'dark', notifications: true }
  }

  describe('Component Rendering', () => {
    it('should render form with all fields', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      expect(wrapper.find('#bio').exists()).toBe(true)
      expect(wrapper.find('#avatar_url').exists()).toBe(true)
      expect(wrapper.find('#preferences').exists()).toBe(true)
    })

    it('should populate fields with initial data', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const bioTextarea = wrapper.find('#bio').element as HTMLTextAreaElement
      const avatarInput = wrapper.find('#avatar_url').element as HTMLInputElement
      const preferencesTextarea = wrapper.find('#preferences').element as HTMLTextAreaElement

      expect(bioTextarea.value).toBe('Test bio')
      expect(avatarInput.value).toBe('https://example.com/avatar.jpg')
      expect(preferencesTextarea.value).toContain('"theme": "dark"')
    })

    it('should render with empty data', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: {}
        }
      })

      const bioTextarea = wrapper.find('#bio').element as HTMLTextAreaElement
      expect(bioTextarea.value).toBe('')
    })
  })

  describe('Bio Field', () => {
    it('should update bio when typing', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const bioTextarea = wrapper.find('#bio')
      await bioTextarea.setValue('Updated bio text')

      expect((bioTextarea.element as HTMLTextAreaElement).value).toBe('Updated bio text')
    })

    it('should show character count', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: { bio: 'Test' }
        }
      })

      expect(wrapper.text()).toContain('4 / 500 characters')
    })

    it('should enforce maxlength of 500 characters', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const bioTextarea = wrapper.find('#bio')
      expect(bioTextarea.attributes('maxlength')).toBe('500')
    })
  })

  describe('Avatar URL Field', () => {
    it('should update avatar URL when typing', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const avatarInput = wrapper.find('#avatar_url')
      await avatarInput.setValue('https://example.com/new-avatar.jpg')

      expect((avatarInput.element as HTMLInputElement).value).toBe(
        'https://example.com/new-avatar.jpg'
      )
    })

    it('should show avatar preview when URL is provided', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const img = wrapper.find('img[alt="Avatar preview"]')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('https://example.com/avatar.jpg')
    })

    it('should not show avatar preview when URL is empty', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: { bio: 'Test' }
        }
      })

      const img = wrapper.find('img[alt="Avatar preview"]')
      expect(img.exists()).toBe(false)
    })

    it('should enforce maxlength of 255 characters', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const avatarInput = wrapper.find('#avatar_url')
      expect(avatarInput.attributes('maxlength')).toBe('255')
    })
  })

  describe('Preferences Field', () => {
    it('should display preferences as formatted JSON', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const preferencesTextarea = wrapper.find('#preferences').element as HTMLTextAreaElement
      const parsed = JSON.parse(preferencesTextarea.value)

      expect(parsed).toEqual({ theme: 'dark', notifications: true })
    })

    it('should show error for invalid JSON', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const preferencesTextarea = wrapper.find('#preferences')
      await preferencesTextarea.setValue('{ invalid json }')

      expect(wrapper.text()).toContain('Invalid JSON format')
    })

    it('should not show error for valid JSON', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      const preferencesTextarea = wrapper.find('#preferences')
      await preferencesTextarea.setValue('{"valid": "json"}')

      expect(wrapper.text()).not.toContain('Invalid JSON format')
    })
  })

  describe('Form Submission', () => {
    it('should emit submit event with updated data', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      await wrapper.find('#bio').setValue('New bio')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')).toBeTruthy()
      const submitData = wrapper.emitted('submit')![0][0] as ProfileUpdate
      expect(submitData.bio).toBe('New bio')
    })

    it('should not submit when JSON is invalid', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      await wrapper.find('#preferences').setValue('{ invalid }')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')).toBeFalsy()
    })

    it('should convert empty strings to null', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      await wrapper.find('#bio').setValue('')
      await wrapper.find('#avatar_url').setValue('')
      await wrapper.find('form').trigger('submit')

      const submitData = wrapper.emitted('submit')![0][0] as ProfileUpdate
      expect(submitData.bio).toBeNull()
      expect(submitData.avatar_url).toBeNull()
    })
  })

  describe('Cancel Action', () => {
    it('should emit cancel event when cancel button is clicked', async () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData
        }
      })

      await wrapper.findAll('button')[1].trigger('click') // Cancel button

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })
  })

  describe('Loading State', () => {
    it('should disable submit button when loading', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData,
          loading: true
        }
      })

      const submitButton = wrapper.find('button[type="submit"]')
      expect(submitButton.attributes('disabled')).toBeDefined()
    })

    it('should show loading text when loading', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData,
          loading: true
        }
      })

      expect(wrapper.text()).toContain('Saving...')
    })

    it('should show normal text when not loading', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData,
          loading: false
        }
      })

      expect(wrapper.text()).toContain('Save Changes')
      expect(wrapper.text()).not.toContain('Saving...')
    })
  })

  describe('Error Display', () => {
    it('should display error message when error prop is provided', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData,
          error: 'Failed to save profile'
        }
      })

      expect(wrapper.text()).toContain('Failed to save profile')
    })

    it('should not display error when error prop is null', () => {
      const wrapper = mount(ProfileEditor, {
        props: {
          initialData: mockInitialData,
          error: null
        }
      })

      expect(wrapper.find('.text-red-500').exists()).toBe(false)
    })
  })
})
