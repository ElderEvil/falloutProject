import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import LoginForm from '@/modules/auth/components/LoginForm.vue';
import { useAuthStore } from '@/stores/auth';

describe('LoginForm', () => {
  let router: any;
  let authStore: any;

  beforeEach(() => {
    setActivePinia(createPinia());
    authStore = useAuthStore();

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', component: LoginForm },
        { path: '/register', component: { template: '<div>Register</div>' } }
      ]
    });
  });

  describe('Rendering', () => {
    it('should render login form with all elements', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.find('h2').text()).toBe('Login');
      expect(wrapper.find('#username').exists()).toBe(true);
      expect(wrapper.find('#password').exists()).toBe(true);
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true);
    });

    it('should have email input with correct attributes', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const emailInput = wrapper.find('#username');
      expect(emailInput.attributes('type')).toBe('email');
      expect(emailInput.attributes('required')).toBeDefined();
    });

    it('should have password input with correct attributes', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      expect(passwordInput.attributes('type')).toBe('password');
      expect(passwordInput.attributes('required')).toBeDefined();
    });
  });

  describe('Form Interaction', () => {
    it('should bind username input correctly', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const usernameInput = wrapper.find('#username');
      await usernameInput.setValue('test@test.com');

      expect((usernameInput.element as HTMLInputElement).value).toBe('test@test.com');
    });

    it('should bind password input correctly', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      await passwordInput.setValue('password123');

      expect((passwordInput.element as HTMLInputElement).value).toBe('password123');
    });

    it('should not display error message initially', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      expect(wrapper.text()).not.toContain('Invalid username or password');
    });
  });

  describe('Form Submission', () => {
    it('should call login with correct credentials on submit', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const loginSpy = vi.spyOn(authStore, 'login').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('test@test.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(loginSpy).toHaveBeenCalledWith('test@test.com', 'password123');
      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should redirect to home on successful login', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(true);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('test@test.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).toHaveBeenCalledWith('/');
    });

    it('should display error message on login failure', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(false);

      await wrapper.find('#username').setValue('wrong@test.com');
      await wrapper.find('#password').setValue('wrongpassword');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(wrapper.text()).toContain('Invalid username or password');
    });

    it('should not redirect on failed login', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      vi.spyOn(authStore, 'login').mockResolvedValue(false);
      const pushSpy = vi.spyOn(router, 'push');

      await wrapper.find('#username').setValue('wrong@test.com');
      await wrapper.find('#password').setValue('wrongpassword');
      await wrapper.find('form').trigger('submit.prevent');

      await flushPromises();

      expect(pushSpy).not.toHaveBeenCalled();
    });

    it('should clear error message on new submission', async () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      // First failed login
      vi.spyOn(authStore, 'login').mockResolvedValue(false);
      await wrapper.find('#username').setValue('wrong@test.com');
      await wrapper.find('#password').setValue('wrongpassword');
      await wrapper.find('form').trigger('submit.prevent');
      await flushPromises();

      expect(wrapper.text()).toContain('Invalid username or password');

      // Second successful login
      vi.spyOn(authStore, 'login').mockResolvedValue(true);
      await wrapper.find('#username').setValue('test@test.com');
      await wrapper.find('#password').setValue('password123');
      await wrapper.find('form').trigger('submit.prevent');
      await flushPromises();

      // Error should not persist
      const errorElement = wrapper.find('.text-red-500');
      expect(errorElement.exists()).toBe(false);
    });
  });

  describe('Styling', () => {
    it('should have correct container styling', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const container = wrapper.find('.flex.min-h-screen.items-center.justify-center');
      expect(container.exists()).toBe(true);
    });

    it('should apply terminal green theme to heading', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const heading = wrapper.find('h2');
      expect(heading.classes()).toContain('text-green-500');
    });

    it('should have submit button with correct styling', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const button = wrapper.find('button[type="submit"]');
      expect(button.classes()).toContain('bg-green-500');
      expect(button.classes()).toContain('hover:bg-green-400');
    });
  });

  describe('Form Validation', () => {
    it('should have required attribute on username field', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const usernameInput = wrapper.find('#username');
      expect(usernameInput.attributes('required')).toBeDefined();
    });

    it('should have required attribute on password field', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const passwordInput = wrapper.find('#password');
      expect(passwordInput.attributes('required')).toBeDefined();
    });

    it('should have email type for username field', () => {
      const wrapper = mount(LoginForm, {
        global: {
          plugins: [router]
        }
      });

      const usernameInput = wrapper.find('#username');
      expect(usernameInput.attributes('type')).toBe('email');
    });
  });
});
