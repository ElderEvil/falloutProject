export interface UserPreferences {
  theme: 'default' | 'amber' | 'blue'
}

export interface UserState {
  email: string
  username: string
  isAuthenticated: boolean
  preferences?: UserPreferences
}

export interface AuthForm {
  email: string
  username?: string
  password: string
  confirmPassword?: string
}

export interface Token {
  access_token: string
  refresh_token: string
}

export interface LoginForm extends AuthForm {
  rememberMe: boolean
}

export interface RegisterForm extends AuthForm {}

export interface User {
  id: string
  username: string
  email: string
  preferences?: UserPreferences
}

export interface AuthError {
  message: string
  status?: number
}
