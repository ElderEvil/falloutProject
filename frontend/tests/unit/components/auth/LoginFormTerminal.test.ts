import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import LoginFormTerminal from '@/modules/auth/components/LoginFormTerminal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

describe('LoginFormTerminal', () => {
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
        { path: '/login', component: LoginFormTerminal },
        { path: '/register', component: { template: '<div>Register</div>' } },
      ],
    })
  })

  const render = () => mount(LoginFormTerminal, { global: { plugins: [router] } })

  async function signIn(wrapper: VueWrapper, email: string, password: string): Promise<void> {
    const inputs = wrapper.findAll('input')
    await inputs[0]!.setValue(email)
    await inputs[1]!.setValue(password)
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
  }

  describe('Rendering', () => {
    it('should render terminal-style login form with all elements', () => {
      const wrapper = render()

      expect(wrapper.text()).toContain('VAULT-TEC INDUSTRIES')
      expect(wrapper.text()).toContain('Vault Network Access Terminal')
      expect(wrapper.findAll('input').length).toBe(2)
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    })

    it('should display correct version number', () => {
      expect(render().text()).toMatch(/SECURE TERMINAL v\d+\.\d+\.\d+/)
    })

    it('should have terminal-style button with arrow icons', () => {
      const button = render().find('button[type="submit"]')

      expect(button.text()).toContain('AUTHENTICATE')
      expect(button.text()).toContain('►')
      expect(button.text()).toContain('◄')
    })

    it.each([
      ['email', 0],
      ['password', 1],
    ])('should have %s input with correct attributes', (type, index) => {
      const input = render().findAll('input')[index]

      expect(input!.attributes('type')).toBe(type)
      expect(input!.attributes('required')).toBeDefined()
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
  })

  describe('Form Interaction', () => {
    it.each([
      ['username', 0, 'test@vault-tec.com'],
      ['password', 1, 'password123'],
    ])('should bind %s input correctly', async (_label, index, value) => {
      const input = render().findAll('input')[index]!

      await input.setValue(value)

      expect((input.element as HTMLInputElement).value).toBe(value)
    })

    it('should not display error message initially', () => {
      const text = render().text()

      expect(text).not.toContain('ERROR')
      expect(text).not.toContain('ACCESS DENIED')
    })
  })

  describe('Form Submission', () => {
    it('should call login with correct credentials on submit', async () => {
      const wrapper = render()
      const loginSpy = vi.spyOn(authStore, 'login').mockResolvedValue(true)
      const pushSpy = vi.spyOn(router, 'push')

      await signIn(wrapper, 'test@vault-tec.com', 'password123')

      expect(loginSpy).toHaveBeenCalledWith('test@vault-tec.com', 'password123')
      expect(pushSpy).toHaveBeenCalledWith('/')
    })

    it('should redirect to home on successful login', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'login').mockResolvedValue(true)
      const pushSpy = vi.spyOn(router, 'push')

      await signIn(wrapper, 'test@vault-tec.com', 'password123')

      expect(pushSpy).toHaveBeenCalledWith('/')
    })

    it('should display terminal-style error message on login failure', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'login').mockResolvedValue(false)

      await signIn(wrapper, 'wrong@vault-tec.com', 'wrongpassword')

      expect(wrapper.text()).toContain('ERROR')
      expect(wrapper.text()).toContain('ACCESS DENIED')
    })

    it('should not redirect on failed login', async () => {
      const wrapper = render()
      vi.spyOn(authStore, 'login').mockResolvedValue(false)
      const pushSpy = vi.spyOn(router, 'push')

      await signIn(wrapper, 'wrong@vault-tec.com', 'wrongpassword')

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
      expect(wrapper.text()).toContain('AWAITING CREDENTIALS')
    })

    it('should have register link', () => {
      const text = render().text()

      expect(text).toContain('NEW OVERSEER REGISTRATION')
      expect(text).toContain('INITIATE PROTOCOL')
    })
  })
})
