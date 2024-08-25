import apiClient from '../plugins/axios'
import type { AxiosResponse } from 'axios'

interface LoginForm {
  username: string
  password: string
}

interface RegisterForm {
  username: string
  email: string
  password: string
}

interface Token {
  access_token: string
  token_type: string
  refresh_token: string
}

interface User {
  id: string
  username: string
  email: string
}

export const authService = {
  login(form: LoginForm): Promise<AxiosResponse<Token>> {
    return apiClient.post('/login/access-token', new URLSearchParams(form as any))
  },
  register(form: RegisterForm): Promise<AxiosResponse<User>> {
    return apiClient.post('/users/open', form)
  },
  refreshToken(refreshToken: string): Promise<AxiosResponse<Token>> {
    const params = new URLSearchParams()
    params.append('refresh_token', refreshToken)
    return apiClient.post('/login/refresh-token', params)
  }
}
