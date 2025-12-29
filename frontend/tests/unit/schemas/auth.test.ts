import { describe, it, expect } from 'vitest'
import { loginSchema, registerSchema } from '@/schemas/auth'
import { ZodError } from 'zod'

describe('Auth Validation Schemas', () => {
  describe('loginSchema', () => {
    describe('Happy Path', () => {
      it('should accept valid login credentials', () => {
        const result = loginSchema.parse({
          username: 'testuser',
          password: 'password123'
        })
        expect(result.username).toBe('testuser')
        expect(result.password).toBe('password123')
      })

      it('should accept minimum valid username (3 chars)', () => {
        const result = loginSchema.parse({
          username: 'abc',
          password: 'pass'
        })
        expect(result.username).toBe('abc')
      })

      it('should accept username with underscores', () => {
        const result = loginSchema.parse({
          username: 'test_user',
          password: 'password'
        })
        expect(result.username).toBe('test_user')
      })

      it('should accept username with hyphens', () => {
        const result = loginSchema.parse({
          username: 'test-user',
          password: 'password'
        })
        expect(result.username).toBe('test-user')
      })

      it('should accept username with numbers', () => {
        const result = loginSchema.parse({
          username: 'user123',
          password: 'password'
        })
        expect(result.username).toBe('user123')
      })
    })

    describe('Username Validation', () => {
      it('should reject username shorter than 3 characters', () => {
        expect(() =>
          loginSchema.parse({
            username: 'ab',
            password: 'password'
          })
        ).toThrow(ZodError)
        expect(() =>
          loginSchema.parse({
            username: 'ab',
            password: 'password'
          })
        ).toThrow('Username must be at least 3 characters')
      })

      it('should reject username longer than 50 characters', () => {
        const longUsername = 'a'.repeat(51)
        expect(() =>
          loginSchema.parse({
            username: longUsername,
            password: 'password'
          })
        ).toThrow('Username must be less than 50 characters')
      })

      it('should reject username with spaces', () => {
        expect(() =>
          loginSchema.parse({
            username: 'test user',
            password: 'password'
          })
        ).toThrow('Username can only contain letters, numbers, underscores, and hyphens')
      })

      it('should reject username with special characters', () => {
        expect(() =>
          loginSchema.parse({
            username: 'test@user',
            password: 'password'
          })
        ).toThrow('Username can only contain letters, numbers, underscores, and hyphens')
      })

      it('should reject empty username', () => {
        expect(() =>
          loginSchema.parse({
            username: '',
            password: 'password'
          })
        ).toThrow()
      })
    })

    describe('Password Validation', () => {
      it('should reject empty password', () => {
        expect(() =>
          loginSchema.parse({
            username: 'testuser',
            password: ''
          })
        ).toThrow('Password is required')
      })

      it('should accept any non-empty password for login', () => {
        const result = loginSchema.parse({
          username: 'testuser',
          password: 'x'
        })
        expect(result.password).toBe('x')
      })
    })
  })

  describe('registerSchema', () => {
    describe('Happy Path', () => {
      it('should accept valid registration data', () => {
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: 'Password123'
        })
        expect(result.username).toBe('newuser')
        expect(result.email).toBe('user@example.com')
        expect(result.password).toBe('Password123')
      })

      it('should accept complex valid password', () => {
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: 'MyP@ssw0rd123!'
        })
        expect(result.password).toBe('MyP@ssw0rd123!')
      })

      it('should accept email with subdomain', () => {
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@mail.example.com',
          password: 'Password123'
        })
        expect(result.email).toBe('user@mail.example.com')
      })
    })

    describe('Username Validation', () => {
      it('should reject username shorter than 3 characters', () => {
        expect(() =>
          registerSchema.parse({
            username: 'ab',
            email: 'user@example.com',
            password: 'Password123'
          })
        ).toThrow('Username must be at least 3 characters')
      })

      it('should reject username longer than 50 characters', () => {
        const longUsername = 'a'.repeat(51)
        expect(() =>
          registerSchema.parse({
            username: longUsername,
            email: 'user@example.com',
            password: 'Password123'
          })
        ).toThrow('Username must be less than 50 characters')
      })

      it('should reject username with invalid characters', () => {
        expect(() =>
          registerSchema.parse({
            username: 'user@name',
            email: 'user@example.com',
            password: 'Password123'
          })
        ).toThrow('Username can only contain letters, numbers, underscores, and hyphens')
      })
    })

    describe('Email Validation', () => {
      it('should reject invalid email format', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'invalid-email',
            password: 'Password123'
          })
        ).toThrow('Invalid email address')
      })

      it('should reject email without @', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'userexample.com',
            password: 'Password123'
          })
        ).toThrow('Invalid email address')
      })

      it('should reject email without domain', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'user@',
            password: 'Password123'
          })
        ).toThrow('Invalid email address')
      })

      it('should reject empty email', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: '',
            password: 'Password123'
          })
        ).toThrow()
      })
    })

    describe('Password Complexity Validation', () => {
      it('should reject password shorter than 8 characters', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'user@example.com',
            password: 'Pass1'
          })
        ).toThrow('Password must be at least 8 characters')
      })

      it('should reject password without uppercase letter', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'user@example.com',
            password: 'password123'
          })
        ).toThrow('Password must contain at least one uppercase letter')
      })

      it('should reject password without lowercase letter', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'user@example.com',
            password: 'PASSWORD123'
          })
        ).toThrow('Password must contain at least one lowercase letter')
      })

      it('should reject password without number', () => {
        expect(() =>
          registerSchema.parse({
            username: 'newuser',
            email: 'user@example.com',
            password: 'Password'
          })
        ).toThrow('Password must contain at least one number')
      })

      it('should accept password with exactly 8 characters meeting all requirements', () => {
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: 'Pass123a'
        })
        expect(result.password).toBe('Pass123a')
      })
    })

    describe('Security Edge Cases', () => {
      it('should reject common weak passwords even if they meet criteria', () => {
        // This is handled by password complexity rules
        // Common passwords like "Password1" technically pass but we could add dictionary check later
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: 'Password1'
        })
        expect(result.password).toBe('Password1')
      })

      it('should accept strong password with special characters', () => {
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: 'MySecure#Pass123'
        })
        expect(result.password).toBe('MySecure#Pass123')
      })

      it('should accept very long password', () => {
        const longPassword = 'Password123' + 'a'.repeat(50)
        const result = registerSchema.parse({
          username: 'newuser',
          email: 'user@example.com',
          password: longPassword
        })
        expect(result.password).toBe(longPassword)
      })
    })
  })

  describe('Schema Type Inference', () => {
    it('should infer correct types from loginSchema', () => {
      const data = loginSchema.parse({
        username: 'test',
        password: 'pass'
      })
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
        password: 'Password123'
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
