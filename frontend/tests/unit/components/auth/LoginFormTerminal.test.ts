import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import LoginFormTerminal from '@/components/auth/LoginFormTerminal.vue';
import { useAuthStore } from '@/stores/auth';

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon']
  }
}));

describe('LoginFormTerminal', () => {
  let router: any;
  let authStore: any;

  beforeEach(() => {
    setActivePinia(createPinia());
    authStore = useAuthStore();

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', component: LoginFormTerminal },
        { path: '/register', component: { template: '<div>Register</div>' } }
      ]
    });
  });

  describe('Rendering', () => {
    it('should render terminal-style login form with all elements', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('VAULT-TEC INDUSTRIES');
      expect(wrapper.text()).toContain('Vault Network Access Terminal');
      expect(wrapper.find('#username').exists()).toBe(true);
      expect(wrapper.find('#password').exists()).toBe(true);
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true);
    });

    it('should display correct version number', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('v1.10.0');
    });

    it('should have terminal-style button with arrow icons', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const button = wrapper.find('button[type="submit"]');
      expect(button.text()).toContain('AUTHENTICATE');
      expect(button.html()).toContain('►');
      expect(button.html()).toContain('◄');
    });

    it('should have email input with correct attributes', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const emailInput = wrapper.find('#username');
      expect(emailInput.attributes('type')).toBe('email');
      expect(emailInput.attributes('required')).toBeDefined();
    });

    it('should have password input with correct attributes', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      expect(passwordInput.attributes('type')).toBe('password');
      expect(passwordInput.attributes('required')).toBeDefined();
    });

    it('should have scanlines overlay element', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.scanlines').exists()).toBe(true);
    });

    it('should have CRT flicker effect', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.flicker').exists()).toBe(true);
    });

    it('should not have Vault-Tec logo icon', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.logo-vault').exists()).toBe(false);
      expect(wrapper.find('.logo-circle').exists()).toBe(false);
    });
  });

  describe('Form Interaction', () => {
    it('should bind username input correctly', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const usernameInput = wrapper.find('#username');
      await usernameInput.setValue('test@vault-tec.com');

      expect((usernameInput.element as HTMLInputElement).value).toBe('test@vault-tec.com');
    });

    it('should bind password input correctly', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      await passwordInput.setValue('password123');

      expect((passwordInput.element as HTMLInputElement).value).toBe('password123');
    });

    it('should not display error message initially', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).not.toContain('ERROR');
      expect(wrapper.text()).not.toContain('ACCESS DENIED');
    });
  });

  describe('Form Submission', () => {
    it('should call login with correct credentials on submit', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      const loginSpy = vi.spyOn(authStore, 'login').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('test@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(loginSpy).toHaveBeenCalledWith('test@vault-tec.com', 'password123');
      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should redirect to home on successful login', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('test@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should display terminal-style error message on login failure', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(false);

      await wrapper.find('#username').setValue('wrong@vault-tec.com');
      await wrapper.find('#password').setValue('wrongpassword');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(wrapper.text()).toContain('ERROR');
      expect(wrapper.text()).toContain('ACCESS DENIED');
    });

    it('should not redirect on failed login', async () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(false);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('wrong@vault-tec.com');
      await wrapper.find('#password').setValue('wrongpassword');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).not.toHaveBeenCalled();
    });
  });

  describe('Terminal Styling', () => {
    it('should have terminal-themed CSS classes', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.login-container').exists()).toBe(true);
      expect(wrapper.find('.terminal-button').exists()).toBe(true);
      expect(wrapper.find('.terminal-input').exists()).toBe(true);
    });

    it('should have system messages section', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.system-messages').exists()).toBe(true);
      expect(wrapper.text()).toContain('INITIALIZING VAULT-TEC SECURE LOGIN');
      expect(wrapper.text()).toContain('AWAITING CREDENTIALS');
    });

    it('should have register link', () => {
      const wrapper = mount(LoginFormTerminal, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('NEW OVERSEER REGISTRATION');
      expect(wrapper.text()).toContain('INITIATE PROTOCOL');
    });
  });
});
