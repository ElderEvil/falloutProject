export interface UserPreferences {
  theme: 'default' | 'amber' | 'blue';
}

export interface UserState {
  email: string;
  username: string;
  isAuthenticated: boolean;
  preferences?: UserPreferences;
}

export interface AuthForm {
  email: string;
  username?: string;
  password: string;
  confirmPassword?: string;
}
