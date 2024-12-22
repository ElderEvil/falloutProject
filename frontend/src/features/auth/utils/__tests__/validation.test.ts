import { describe, it, expect } from 'vitest';
import { validateEmail, validatePassword, validateLoginForm, validateSignupForm } from '../validation';

describe('Auth Validation Utils', () => {
  describe('validateEmail', () => {
    it('validates correct email formats', () => {
      expect(validateEmail('test@example.com')).toBe(true);
      expect(validateEmail('user.name@domain.co.uk')).toBe(true);
    });

    it('invalidates incorrect email formats', () => {
      expect(validateEmail('test@')).toBe(false);
      expect(validateEmail('test.com')).toBe(false);
      expect(validateEmail('@example.com')).toBe(false);
    });
  });

  describe('validatePassword', () => {
    it('validates passwords with minimum length', () => {
      expect(validatePassword('123456')).toBe(true);
      expect(validatePassword('securepassword')).toBe(true);
    });

    it('invalidates short passwords', () => {
      expect(validatePassword('12345')).toBe(false);
      expect(validatePassword('')).toBe(false);
    });
  });

  describe('validateLoginForm', () => {
    it('validates correct login form', () => {
      const form = {
        email: 'test@example.com',
        password: 'password123'
      };
      expect(validateLoginForm(form).isValid).toBe(true);
    });

    it('invalidates login form with missing fields', () => {
      const form = {
        email: 'test@example.com',
        password: ''
      };
      const result = validateLoginForm(form);
      expect(result.isValid).toBe(false);
      expect(result.message).toBe('Password is required');
    });
  });

  describe('validateSignupForm', () => {
    it('validates correct signup form', () => {
      const form = {
        email: 'test@example.com',
        username: 'testuser',
        password: 'password123',
        confirmPassword: 'password123'
      };
      expect(validateSignupForm(form).isValid).toBe(true);
    });

    it('invalidates signup form with mismatched passwords', () => {
      const form = {
        email: 'test@example.com',
        username: 'testuser',
        password: 'password123',
        confirmPassword: 'password456'
      };
      const result = validateSignupForm(form);
      expect(result.isValid).toBe(false);
      expect(result.message).toBe('Passwords do not match');
    });

    it('invalidates signup form with missing username', () => {
      const form = {
        email: 'test@example.com',
        username: '',
        password: 'password123',
        confirmPassword: 'password123'
      };
      const result = validateSignupForm(form);
      expect(result.isValid).toBe(false);
      expect(result.message).toBe('Username is required');
    });
  });
});
