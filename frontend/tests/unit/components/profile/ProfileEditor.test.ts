import { describe, it, expect, vi } from 'vite-plus/test'
import { mount, flushPromises, type MountingOptions, type VueWrapper } from '@vue/test-utils'
import ProfileEditor from '@/modules/profile/components/ProfileEditor.vue'
import type { ProfileUpdate } from '@/models/profile'
import { authService } from '@/modules/auth/services/authService'

vi.mock('@/modules/auth/services/authService', () => ({
  authService: { requestPasswordReset: vi.fn() },
}))

type ProfileEditorProps = InstanceType<typeof ProfileEditor>['$props']
type MountOptions = Omit<MountingOptions<typeof ProfileEditor>, 'props'>

const mockInitialData = {
  bio: 'Test bio',
  avatar_url: 'https://example.com/avatar.jpg',
  preferences: { theme: 'dark', notifications: true },
}

/** Mounts the editor with the required `initialData` filled; callers override what they need. */
function mountEditor(
  props: Partial<ProfileEditorProps> = {},
  options: MountOptions = {}
): VueWrapper {
  return mount(ProfileEditor, {
    ...options,
    props: { initialData: mockInitialData, ...props } as ProfileEditorProps,
  })
}

function buttonWithText(wrapper: VueWrapper, text: string) {
  const found = wrapper.findAll('button').find((button) => button.text().includes(text))
  if (!found) throw new Error(`No button containing "${text}"`)
  return found
}

describe('ProfileEditor', () => {
  describe('Component Rendering', () => {
    it('should render form with all fields', () => {
      const wrapper = mountEditor()

      expect(wrapper.find('#bio').exists()).toBe(true)
      expect(wrapper.find('#avatar_url').exists()).toBe(true)
      expect(wrapper.find('#preferences').exists()).toBe(true)
    })

    it('uses a warm terminal editor surface with terminal-themed fields', () => {
      const wrapper = mountEditor()

      expect(wrapper.find('.profile-editor').classes()).toContain('bg-surface')
      expect(wrapper.find('#bio').classes()).toContain('bg-surface-sunken')
      expect(wrapper.find('#bio').classes()).toContain('border-theme-primary/30')
    })

    it('should populate fields with initial data', () => {
      const wrapper = mountEditor()

      expect((wrapper.find('#bio').element as HTMLTextAreaElement).value).toBe('Test bio')
      expect((wrapper.find('#avatar_url').element as HTMLInputElement).value).toBe(
        'https://example.com/avatar.jpg'
      )
      expect((wrapper.find('#preferences').element as HTMLTextAreaElement).value).toContain(
        '"theme": "dark"'
      )
    })

    it('should render with empty data', () => {
      const wrapper = mountEditor({ initialData: {} })

      expect((wrapper.find('#bio').element as HTMLTextAreaElement).value).toBe('')
    })
  })

  describe('Bio Field', () => {
    it('should update bio when typing', async () => {
      const bioTextarea = mountEditor().find('#bio')
      await bioTextarea.setValue('Updated bio text')

      expect((bioTextarea.element as HTMLTextAreaElement).value).toBe('Updated bio text')
    })

    it('should show character count', () => {
      expect(mountEditor({ initialData: { bio: 'Test' } }).text()).toContain('4 / 500 characters')
    })

    it('should enforce maxlength of 500 characters', () => {
      expect(mountEditor().find('#bio').attributes('maxlength')).toBe('500')
    })
  })

  describe('Avatar URL Field', () => {
    it('should update avatar URL when typing', async () => {
      const avatarInput = mountEditor().find('#avatar_url')
      await avatarInput.setValue('https://example.com/new-avatar.jpg')

      expect((avatarInput.element as HTMLInputElement).value).toBe(
        'https://example.com/new-avatar.jpg'
      )
    })

    it('should show avatar preview when URL is provided', () => {
      const img = mountEditor().find('img[alt="Avatar preview"]')

      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('https://example.com/avatar.jpg')
    })

    it('should not show avatar preview when URL is empty', () => {
      expect(
        mountEditor({ initialData: { bio: 'Test' } })
          .find('img[alt="Avatar preview"]')
          .exists()
      ).toBe(false)
    })

    it('renders the avatar URL field with the Input primitive', () => {
      expect(mountEditor().find('#avatar_url').attributes('data-slot')).toBe('input')
    })

    it('should enforce maxlength of 255 characters', () => {
      expect(mountEditor().find('#avatar_url').attributes('maxlength')).toBe('255')
    })
  })

  describe('Preferences Field', () => {
    it('should display preferences as formatted JSON', () => {
      const value = (mountEditor().find('#preferences').element as HTMLTextAreaElement).value

      expect(JSON.parse(value)).toEqual({ theme: 'dark', notifications: true })
    })

    it('should show error for invalid JSON', async () => {
      const wrapper = mountEditor()
      await wrapper.find('#preferences').setValue('{ invalid json }')

      expect(wrapper.text()).toContain('Invalid JSON format')
      expect((wrapper.find('details').element as HTMLDetailsElement).open).toBe(true)
    })

    it('should not show error for valid JSON', async () => {
      const wrapper = mountEditor()
      await wrapper.find('#preferences').setValue('{"valid": "json"}')

      expect(wrapper.text()).not.toContain('Invalid JSON format')
    })
  })

  describe('Form Submission', () => {
    it('should emit submit event with updated data', async () => {
      const wrapper = mountEditor()

      await wrapper.find('#bio').setValue('New bio')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')).toBeTruthy()
      const submitData = wrapper.emitted('submit')![0][0] as ProfileUpdate
      expect(submitData.bio).toBe('New bio')
    })

    it('should not submit when JSON is invalid', async () => {
      const wrapper = mountEditor()

      await wrapper.find('#preferences').setValue('{ invalid }')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')).toBeFalsy()
    })

    it('should convert empty strings to null', async () => {
      const wrapper = mountEditor()

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
      const wrapper = mountEditor()

      // The theme Select renders its trigger as a button, so locate Cancel by label.
      await buttonWithText(wrapper, 'Cancel').trigger('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })
  })

  describe('Loading State', () => {
    it('should disable submit button when loading', () => {
      const submitButton = mountEditor({ loading: true }).find('button[type="submit"]')

      expect(submitButton.attributes('disabled')).toBeDefined()
    })

    it('should show loading text when loading', () => {
      expect(mountEditor({ loading: true }).text()).toContain('Saving...')
    })

    it('should show normal text when not loading', () => {
      const text = mountEditor({ loading: false }).text()

      expect(text).toContain('Save Changes')
      expect(text).not.toContain('Saving...')
    })
  })

  describe('Email Field', () => {
    const withEmail = () => mountEditor({ email: 'old@test.com' })

    it('renders the current email', () => {
      expect((withEmail().find('#email').element as HTMLInputElement).value).toBe('old@test.com')
    })

    it('emits a changed email as the third submit argument', async () => {
      const wrapper = withEmail()

      await wrapper.find('#email').setValue('new@test.com')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')?.[0]?.[2]).toBe('new@test.com')
    })

    it('does not emit an email when it is unchanged', async () => {
      const wrapper = withEmail()

      await wrapper.find('form').trigger('submit')

      expect(wrapper.emitted('submit')?.[0]?.[2]).toBeNull()
    })

    it('blocks submission and explains an invalid address', async () => {
      const wrapper = withEmail()

      await wrapper.find('#email').setValue('not-an-email')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.text()).toContain('Enter a valid email address.')
      expect(wrapper.emitted('submit')).toBeFalsy()
    })
  })

  describe('Error Display', () => {
    it('should display error message when error prop is provided', () => {
      expect(mountEditor({ error: 'Failed to save profile' }).text()).toContain(
        'Failed to save profile'
      )
    })

    it('should not display error when error prop is null', () => {
      expect(mountEditor({ error: null }).find('.text-red-500').exists()).toBe(false)
    })
  })
})

describe('Sign-in methods', () => {
  it('offers adding a password for passwordless accounts', async () => {
    const wrapper = mountEditor({
      initialData: { bio: 'Test bio' },
      email: 'overseer@example.com',
      hasPassword: false,
    })

    expect(wrapper.text()).toContain("We'll email you a link to set a password")
    await buttonWithText(wrapper, 'ADD PASSWORD').trigger('click')
    await flushPromises()

    expect(authService.requestPasswordReset).toHaveBeenCalledWith('overseer@example.com')
    expect(wrapper.text()).toContain('EMAIL SENT')
  })

  it('states when password sign-in is enabled', () => {
    const text = mountEditor({ initialData: { bio: 'Test bio' }, hasPassword: true }).text()

    expect(text).toContain('Password sign-in is enabled')
    expect(text).toContain(
      'Changing your email does not change which Google or GitHub identity is linked'
    )
  })
})
