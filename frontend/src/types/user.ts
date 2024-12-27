export interface UserPreferences {
  theme: 'default' | 'amber' | 'blue';
}

export interface User {
  id?: string;
  username: string;
  email: string;
  preferences?: UserPreferences;
  isAuthenticated: boolean;
}
