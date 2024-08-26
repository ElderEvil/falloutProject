export interface LoginForm {
  username: string
  password: string
}

export interface RegisterForm {
  username: string
  email: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
  refresh_token: string | null
}

export class AuthError extends Error {
  constructor(
    message: string,
    public code?: number
  ) {
    super(message)
    this.name = 'AuthError'
  }
}
