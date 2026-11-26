import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import RegisterForm from '@/modules/auth/components/RegisterForm.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

const credentials = {
  username: 'overseer',
  email: 'overseer@vault-tec.com',
  password: 'password123',
  confirm: 'password123',
}

describe('RegisterForm', () => {
  let router: Router
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    authStore = useAuthStore()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', component: { template: '<div>Login</div>' } },
        { path: '/register', component: RegisterForm },
      ],
    })
  })

  function render(): VueWrapper {
    return mount(RegisterForm, { global: { plugins: [router] } })
  }

  async function fill(
    wrapper: VueWrapper,
    overrides: Partial<typeof credentials> = {}
  ): Promise<VueWrapper<'input', HTMLInputElement>[]> {
    const values = { ...credentials, ...overrides }
    const inputs = wrapper.findAll<'input', HTMLInputElement>('input')
    await inputs[0]!.setValue(values.username)
    await inputs[1]!.setValue(values.email)
    await inputs[2]!.setValue(values.password)
    await inputs[3]!.setValue(values.confirm)
    return inputs
  }

  async function submit(wrapper: VueWrapper): Promise<void> {
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
  }

  function buttonWithText(wrapper: VueWrapper, text: string) {
    const found = wrapper.findAll('button').find((button) => button.text().includes(text))
    if (!found) throw new Error(`No button containing "${text}"`)
    return found
  }

  describe('Rendering', () => {
    it('should render terminal-style register form with all elements', () => {
      const wrapper = render()

      expect(wrapper.text()).toContain('VAULT-TEC INDUSTRIES')
      expect(wrapper.text()).toContain('New Overseer Registration Terminal')
      expect(wrapper.findAll('input').length).toBe(4)
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    })

    it('should display correct version number', () => {
      expect(render().text()).toMatch(/v?\d+\.\d+\.\d+/)
    })

    it('should have terminal-style button with arrow icons', () => {
      const button = render().find('button[type="submit"]')

      expect(button.text()).toContain('REGISTER OVERSEER')
      expect(button.text()).toContain('►')
      expect(button.text()).toContain('◄')
    })

    it('should have all required input fields', () => {
      const inputs = render().findAll('input')

      expect(inputs[0]!.attributes('required')).toBeDefined()
      expect(inputs[1]!.attributes('required')).toBeDefined()
      expect(inputs[2]!.attributes('required')).toBeDefined()
      expect(inputs[3]!.attributes('required')).toBeDefined()
    })

    it('should not render per-view scanlines overlay (moved to DefaultLayout)', () => {
      expect(render().find('.scanlines').exists()).toBe(false)
    })

    it('respects the saved flicker setting', () => {
      localStorage.setItem('visual-effects:flickering', 'true')

      expect(render().find('.flicker').exists()).toBe(true)
    })

    it('should not have Vault-Tec logo icon', () => {
      const wrapper = render()

      expect(wrapper.find('.logo-vault').exists()).toBe(false)
      expect(wrapper.find('.logo-circle').exists()).toBe(false)
    })

    it('should have login link', () => {
      const wrapper = render()

      expect(wrapper.text()).toContain('EXISTING OVERSEER LOGIN')
      expect(wrapper.text()).toContain('ACCESS TERMINAL')
    })
  })

  describe('Form Interaction', () => {
    it.each([
      ['the username input', 0, 'overseer'],
      ['the email input', 1, 'overseer@vault-tec.com'],
    ])('should bind %s correctly', async (_label, index, value) => {
      const input = render().findAll('input')[index]!

      await input.setValue(value)

      expect((input.element as HTMLInputElement).value).toBe(value)
    })

    it('should bind password inputs correctly', async () => {
      const wrapper = render()
      const passwordInput = wrapper.findAll('input')[2]!
      const confirmInput = wrapper.findAll('input')[3]!

      await passwordInput.setValue('password123')
      await confirmInput.setValue('password123')

      expect((passwordInput.element as HTMLInputElement).value).toBe('password123')
      expect((confirmInput.element as HTMLInputElement).value).toBe('password123')
    })

    it('should not display error message initially', () => {
      expect(render().text()).not.toContain('ERROR')
    })
  })

  describe('Form Validation', () => {
    it.each([
      ['the passwords do not match', { confirm: 'different' }, /PASSWORDS DO NOT MATCH/],
      [
        'the password is shorter than 8 characters',
        { password: 'short', confirm: 'short' },
        /at least 8|too short/i,
      ],
      [
        'the email format is invalid',
        { email: 'notanemail', password: 'longenoughpassword', confirm: 'longenoughpassword' },
        /valid email|invalid email/i,
      ],
    ])('reports the error and skips register when %s', async (_label, overrides, message) => {
      const wrapper = render()
      const registerSpy = vi.spyOn(authStore, 'register')

      await fill(wrapper, overrides)
      await submit(wrapper)

      expect(wrapper.text()).toMatch(message)
      expect(registerSpy).not.toHaveBeenCalled()
    })
  })

  describe('Form Submission', () => {
    async function submitValidRegistration(wrapper: VueWrapper): Promise<void> {
      await fill(wrapper)
      await submit(wrapper)
    }

    it('should call register with correct data on submit', async () => {
      const wrapper = render()
      const registerSpy = vi.spyOn(authStore, 'register').mockResolvedValue(true)
      const pushSpy = vi.spyOn(router, 'push')

      await submitValidRegistration(wrapper)

      expect(registerSpy).toHaveBeenCalledWith('overseer', 'overseer@vault-tec.com', 'password123')
      expect(wrapper.text()).toContain('CHECK YOUR EMAIL')
      expect(pushSpy).not.toHaveBeenCalled()
    })

    it('should show the inline check-your-email panel on successful registration', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'register').mockResolvedValue(true)
      const pushSpy = vi.spyOn(router, 'push')

      await submitValidRegistration(wrapper)

      expect(wrapper.text()).toContain('CHECK YOUR EMAIL')
      expect(wrapper.text()).toContain('CONTINUE TO VAULT')
      expect(pushSpy).not.toHaveBeenCalled()
    })

    it('should resend the verification email from the success panel', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'register').mockResolvedValue(true)
      const resendSpy = vi.spyOn(authStore, 'resendVerificationEmail').mockResolvedValue(true)

      await submitValidRegistration(wrapper)
      await buttonWithText(wrapper, 'RESEND EMAIL').trigger('click')
      await flushPromises()

      expect(resendSpy).toHaveBeenCalledOnce()
      expect(wrapper.text()).toContain('EMAIL SENT')
    })

    it('should continue to the vault from the success panel', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'register').mockResolvedValue(true)
      const pushSpy = vi.spyOn(router, 'push')

      await submitValidRegistration(wrapper)
      await buttonWithText(wrapper, 'CONTINUE TO VAULT').trigger('click')
      await flushPromises()

      expect(pushSpy).toHaveBeenCalledWith('/')
    })

    it('should display terminal-style error message on registration failure', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'register').mockResolvedValue(false)

      await submitValidRegistration(wrapper)

      expect(wrapper.text()).toContain('ERROR')
      expect(wrapper.text()).toContain('REGISTRATION FAILED')
    })

    it('should not redirect on failed registration', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'register').mockResolvedValue(false)
      const pushSpy = vi.spyOn(router, 'push')

      await submitValidRegistration(wrapper)

      expect(pushSpy).not.toHaveBeenCalled()
    })
  })

  describe('Terminal Styling', () => {
    it('should have terminal-themed CSS classes', () => {
      const wrapper = render()

      expect(wrapper.find('[data-slot="card"]').exists()).toBe(true)
      expect(wrapper.find('button').exists()).toBe(true)
      expect(wrapper.find('input').exists()).toBe(true)
    })

    it('should have system messages section', () => {
      const wrapper = render()

      expect(wrapper.find('.system-messages').exists()).toBe(true)
      expect(wrapper.text()).toContain('SECURE TERMINAL')
      expect(wrapper.text()).toContain('AWAITING REGISTRATION DATA')
    })

    it('should have terminal-style labels', () => {
      const text = render().text()

      expect(text).toContain('OVERSEER USERNAME')
      expect(text).toContain('EMAIL ADDRESS')
      expect(text).toContain('SECURITY PASSPHRASE')
      expect(text).toContain('CONFIRM PASSPHRASE')
    })
  })
})
