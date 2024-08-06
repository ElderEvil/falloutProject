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
}

interface User {
  id: string
  username: string
  email: string
}
