export interface AuthForm {
  email: string;
  username?: string;
  password: string;
  confirmPassword?: string;
}

export interface UserPreferences {
  theme: string;
}

export interface UserState {
  email: string;
  username: string;
  isAuthenticated: boolean;
  preferences?: UserPreferences;
}
