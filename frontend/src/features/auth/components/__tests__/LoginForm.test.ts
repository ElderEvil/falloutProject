import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import LoginForm from '../LoginForm.vue';
import { useAuthStore } from '../../store/auth';

describe('LoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly', () => {
    const wrapper = mount(LoginForm, {
      global: {
        plugins: [createTestingPinia()]
      }
    });

    expect(wrapper.find('n-form').exists()).toBe(true);
    expect(wrapper.findAll('n-form-item')).toHaveLength(2);
  });

  it('handles form submission', async () => {
    const wrapper = mount(LoginForm, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn
        })]
      }
    });

    const store = useAuthStore();
    const loginSpy = vi.spyOn(store, 'login');

    await wrapper.find('input[type="email"]').setValue('test@example.com');
    await wrapper.find('input[type="password"]').setValue('password123');
    await wrapper.find('button').trigger('click');

    expect(loginSpy).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password123'
    });
  });

  it('shows error message on failed login', async () => {
    const wrapper = mount(LoginForm, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            auth: {
              user: {
                isAuthenticated: false
              }
            }
          }
        })]
      }
    });

    const store = useAuthStore();
    vi.spyOn(store, 'login').mockResolvedValue({
      success: false,
      message: 'Invalid credentials'
    });

    await wrapper.find('button').trigger('click');

    // Check if error message is displayed
    // Note: In a real app, you'd need to mock the Naive UI message component
    expect(wrapper.emitted('error')).toBeTruthy();
  });
});
