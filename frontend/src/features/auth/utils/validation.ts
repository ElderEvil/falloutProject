import type { AuthForm } from '../model/types'

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

export function validatePassword(password: string): boolean {
  return password.length >= 6
}

export function validateSignupForm(form: AuthForm): { isValid: boolean; message?: string } {
  if (!validateEmail(form.email)) {
    return { isValid: false, message: 'Invalid email format' }
  }

  if (!form.username) {
    return { isValid: false, message: 'Username is required' }
  }

  if (!form.password) {
    return { isValid: false, message: 'Password is required' }
  }

  if (form.password !== form.confirmPassword) {
    return { isValid: false, message: 'Passwords do not match' }
  }

  if (!validatePassword(form.password)) {
    return { isValid: false, message: 'Password must be at least 6 characters' }
  }

  return { isValid: true }
}

export function validateLoginForm(form: AuthForm): { isValid: boolean; message?: string } {
  if (!validateEmail(form.email)) {
    return { isValid: false, message: 'Invalid email format' }
  }

  if (!form.password) {
    return { isValid: false, message: 'Password is required' }
  }

  return { isValid: true }
}
