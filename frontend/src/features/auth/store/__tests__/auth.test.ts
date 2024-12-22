import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '../auth';

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('initializes with default state', () => {
    const store = useAuthStore();
    expect(store.user).toEqual({
      email: '',
      username: '',
      isAuthenticated: false,
      preferences: {
        theme: 'default'
      }
    });
  });

  it('handles successful login', async () => {
    const store = useAuthStore();
    const loginForm = {
      email: 'test@example.com',
      password: 'password123'
    };

    const result = await store.login(loginForm);

    expect(result.success).toBe(true);
    expect(store.user.isAuthenticated).toBe(true);
    expect(store.user.email).toBe('test@example.com');
  });

  it('handles failed login with invalid email', async () => {
    const store = useAuthStore();
    const loginForm = {
      email: 'invalid-email',
      password: 'password123'
    };

    const result = await store.login(loginForm);

    expect(result.success).toBe(false);
    expect(result.message).toBe('Invalid email format');
    expect(store.user.isAuthenticated).toBe(false);
  });

  it('handles logout', () => {
    const store = useAuthStore();

    // First login
    store.user.isAuthenticated = true;
    store.user.email = 'test@example.com';

    // Then logout
    store.logout();

    expect(store.user.isAuthenticated).toBe(false);
    expect(store.user.email).toBe('');
  });
});
