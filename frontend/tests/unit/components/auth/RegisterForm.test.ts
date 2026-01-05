import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory} from 'vue-router';
import RegisterForm from '@/components/auth/RegisterForm.vue';
import { useAuthStore } from '@/stores/auth';

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon']
  }
}));

describe('RegisterForm', () => {
  let router: any;
  let authStore: any;

  beforeEach(() => {
    setActivePinia(createPinia());
    authStore = useAuthStore();

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', component: { template: '<div>Login</div>' } },
        { path: '/register', component: RegisterForm }
      ]
    });
  });

  describe('Rendering', () => {
    it('should render terminal-style register form with all elements', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('VAULT-TEC INDUSTRIES');
      expect(wrapper.text()).toContain('New Overseer Registration Terminal');
      expect(wrapper.find('#username').exists()).toBe(true);
      expect(wrapper.find('#email').exists()).toBe(true);
      expect(wrapper.find('#password').exists()).toBe(true);
      expect(wrapper.find('#confirmPassword').exists()).toBe(true);
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true);
    });

    it('should display correct version number', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('v1.10.0');
    });

    it('should have terminal-style button with arrow icons', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const button = wrapper.find('button[type="submit"]');
      expect(button.text()).toContain('REGISTER OVERSEER');
      expect(button.html()).toContain('►');
      expect(button.html()).toContain('◄');
    });

    it('should have all required input fields', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('#username').attributes('required')).toBeDefined();
      expect(wrapper.find('#email').attributes('required')).toBeDefined();
      expect(wrapper.find('#password').attributes('required')).toBeDefined();
      expect(wrapper.find('#confirmPassword').attributes('required')).toBeDefined();
    });

    it('should have scanlines overlay element', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.scanlines').exists()).toBe(true);
    });

    it('should have CRT flicker effect', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.flicker').exists()).toBe(true);
    });

    it('should not have Vault-Tec logo icon', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.logo-vault').exists()).toBe(false);
      expect(wrapper.find('.logo-circle').exists()).toBe(false);
    });

    it('should have login link', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('EXISTING OVERSEER LOGIN');
      expect(wrapper.text()).toContain('ACCESS TERMINAL');
    });
  });

  describe('Form Interaction', () => {
    it('should bind username input correctly', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const usernameInput = wrapper.find('#username');
      await usernameInput.setValue('overseer');

      expect((usernameInput.element as HTMLInputElement).value).toBe('overseer');
    });

    it('should bind email input correctly', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const emailInput = wrapper.find('#email');
      await emailInput.setValue('overseer@vault-tec.com');

      expect((emailInput.element as HTMLInputElement).value).toBe('overseer@vault-tec.com');
    });

    it('should bind password inputs correctly', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      const confirmInput = wrapper.find('#confirmPassword');

      await passwordInput.setValue('password123');
      await confirmInput.setValue('password123');

      expect((passwordInput.element as HTMLInputElement).value).toBe('password123');
      expect((confirmInput.element as HTMLInputElement).value).toBe('password123');
    });

    it('should not display error message initially', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).not.toContain('ERROR');
    });
  });

  describe('Form Validation', () => {
    it('should show error when passwords do not match', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('different');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(wrapper.text()).toContain('PASSWORDS DO NOT MATCH');
    });

    it('should not call register when passwords do not match', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const registerSpy = vi.spyOn(authStore, 'register');

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('different');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(registerSpy).not.toHaveBeenCalled();
    });
  });

  describe('Form Submission', () => {
    it('should call register with correct data on submit', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      const registerSpy = vi.spyOn(authStore, 'register').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(registerSpy).toHaveBeenCalledWith('overseer', 'overseer@vault-tec.com', 'password123');
      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should redirect to home on successful registration', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'register').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should display terminal-style error message on registration failure', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'register').mockResolvedValue(false);

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(wrapper.text()).toContain('ERROR');
      expect(wrapper.text()).toContain('REGISTRATION FAILED');
    });

    it('should not redirect on failed registration', async () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'register').mockResolvedValue(false);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('overseer');
      await wrapper.find('#email').setValue('overseer@vault-tec.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('#confirmPassword').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).not.toHaveBeenCalled();
    });
  });

  describe('Terminal Styling', () => {
    it('should have terminal-themed CSS classes', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.register-container').exists()).toBe(true);
      expect(wrapper.find('.terminal-button').exists()).toBe(true);
      expect(wrapper.find('.terminal-input').exists()).toBe(true);
    });

    it('should have system messages section', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('.system-messages').exists()).toBe(true);
      expect(wrapper.text()).toContain('INITIALIZING NEW OVERSEER REGISTRATION');
      expect(wrapper.text()).toContain('AWAITING REGISTRATION DATA');
    });

    it('should have terminal-style labels', () => {
      const wrapper = mount(RegisterForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).toContain('OVERSEER USERNAME');
      expect(wrapper.text()).toContain('EMAIL ADDRESS');
      expect(wrapper.text()).toContain('SECURITY PASSPHRASE');
      expect(wrapper.text()).toContain('CONFIRM PASSPHRASE');
    });
  });
});
