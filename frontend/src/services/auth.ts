import axios from '@/plugins/axios';
import type { User } from '@/types/user';

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export const login = async (username: string, password: string): Promise<AuthTokens> => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await axios.post<AuthTokens>('/api/v1/login/access-token', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return response.data;
};

export const register = async (
  username: string,
  email: string,
  password: string
): Promise<AuthTokens> => {
  const response = await axios.post<AuthTokens>('/api/v1/users/open', {
    username,
    email,
    password
  });
  return response.data;
};

export const fetchUser = async (token: string): Promise<User> => {
  const response = await axios.get<User>('/api/v1/users/me', {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data;
};

export const refreshAccessToken = async (refreshToken: string): Promise<string> => {
  const formData = new URLSearchParams();
  formData.append('refresh_token', refreshToken);

  const response = await axios.post<Pick<AuthTokens, 'access_token'>>(
    '/api/v1/login/refresh-token',
    formData,
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }
  );
  return response.data.access_token;
};

export const logout = async (token: string): Promise<void> => {
  await axios.post(
    '/api/v1/logout',
    {},
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  );
};
