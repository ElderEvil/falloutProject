import { describe, it, expect } from 'vite-plus/test'
import { loginSchema, registerSchema } from '@/modules/auth/schemas/auth'
import { ZodError } from 'zod'

const login = (username: string, password = 'password') => loginSchema.parse({ username, password })

const register = (overrides: Partial<{ username: string; email: string; password: string }> = {}) =>
  registerSchema.parse({
    username: 'newuser',
    email: 'user@example.com',
    password: 'Password123',
    ...overrides,
  })

/** Every rejection is a ZodError carrying the schema's own message. */
function expectRejection(parse: () => unknown, message: string): void {
  expect(parse).toThrow(ZodError)
  expect(parse).toThrow(message)
}

const USERNAME_CHARSET = 'Username can only contain letters, numbers, underscores, and hyphens'

describe('Auth Validation Schemas', () => {
  describe('loginSchema', () => {
    describe('Happy Path', () => {
      it.each(['testuser', 'abc', 'test_user', 'test-user', 'user123'])(
        'accepts the username %s',
        (username) => {
          expect(login(username).username).toBe(username)
        }
      )

      it('accepts a password and returns it unchanged', () => {
        const result = loginSchema.parse({ username: 'testuser', password: 'password123' })

        expect(result.username).toBe('testuser')
        expect(result.password).toBe('password123')
      })

      it('should accept any non-empty password for login', () => {
        expect(login('testuser', 'x').password).toBe('x')
      })
    })

    describe('Username Validation', () => {
      it.each([
        ['shorter than 3 characters', 'ab', 'Username must be at least 3 characters'],
        ['longer than 50 characters', 'a'.repeat(51), 'Username must be less than 50 characters'],
        ['with spaces', 'test user', USERNAME_CHARSET],
        ['with special characters', 'test@user', USERNAME_CHARSET],
        ['empty', '', 'Username must be at least 3 characters'],
      ])('rejects a username %s', (_label, username, message) => {
        expectRejection(() => login(username), message)
      })
    })

    describe('Password Validation', () => {
      it('should reject empty password', () => {
        expectRejection(() => login('testuser', ''), 'Password is required')
      })
    })
  })

  describe('registerSchema', () => {
    describe('Happy Path', () => {
      it('should accept valid registration data', () => {
        const result = register()

        expect(result.username).toBe('newuser')
        expect(result.email).toBe('user@example.com')
        expect(result.password).toBe('Password123')
      })

      it.each(['MyP@ssw0rd123!', 'MySecure#Pass123', 'Password123' + 'a'.repeat(50), 'Password1'])(
        'accepts the password %s',
        (password) => {
          expect(register({ password }).password).toBe(password)
        }
      )

      it('should accept email with subdomain', () => {
        expect(register({ email: 'user@mail.example.com' }).email).toBe('user@mail.example.com')
      })

      it('should accept password with exactly 8 characters meeting all requirements', () => {
        expect(register({ password: 'Pass123a' }).password).toBe('Pass123a')
      })
    })

    describe('Username Validation', () => {
      it.each([
        ['shorter than 3 characters', 'ab', 'Username must be at least 3 characters'],
        ['longer than 50 characters', 'a'.repeat(51), 'Username must be less than 50 characters'],
        ['with invalid characters', 'user@name', USERNAME_CHARSET],
      ])('rejects a username %s', (_label, username, message) => {
        expectRejection(() => register({ username }), message)
      })
    })

    describe('Email Validation', () => {
      it.each(['invalid-email', 'userexample.com', 'user@', ''])(
        'rejects the email %s',
        (email) => {
          expectRejection(() => register({ email }), 'Invalid email address')
        }
      )
    })

    describe('Password Complexity Validation', () => {
      it.each([
        ['shorter than 8 characters', 'Pass1', 'Password must be at least 8 characters'],
        [
          'without uppercase letter',
          'password123',
          'Password must contain at least one uppercase letter',
        ],
        [
          'without lowercase letter',
          'PASSWORD123',
          'Password must contain at least one lowercase letter',
        ],
        ['without number', 'Password', 'Password must contain at least one number'],
      ])('rejects a password %s', (_label, password, message) => {
        expectRejection(() => register({ password }), message)
      })
    })
  })

  describe('Schema Type Inference', () => {
    it('should infer correct types from loginSchema', () => {
      const data = loginSchema.parse({ username: 'test', password: 'pass' })
      // TypeScript should infer these as strings
      const username: string = data.username
      const password: string = data.password

      expect(username).toBe('test')
      expect(password).toBe('pass')
    })

    it('should infer correct types from registerSchema', () => {
      const data = registerSchema.parse({
        username: 'test',
        email: 'test@example.com',
        password: 'Password123',
      })
      // TypeScript should infer these as strings
      const username: string = data.username
      const email: string = data.email
      const password: string = data.password

      expect(username).toBe('test')
      expect(email).toBe('test@example.com')
      expect(password).toBe('Password123')
    })
  })
})
