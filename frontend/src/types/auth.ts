export interface AuthForm {
  email: string;
  username?: string;
  password: string;
  confirmPassword?: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
}

export interface LoginForm extends AuthForm {
  rememberMe: boolean;
}

export interface RegisterForm extends AuthForm {}
