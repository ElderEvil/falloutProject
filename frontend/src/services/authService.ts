import apiClient from "../plugins/axios";
import type { AxiosResponse } from "axios";
import { AuthError, type Token } from "@/types/auth";
import type { User } from "@/types/user";
import type { LoginFormData, RegisterFormData } from "@/schemas/auth";

export const authService = {
  async login(form: LoginFormData): Promise<AxiosResponse<Token>> {
    try {
      const formAsRecord: Record<string, string> = {
        username: form.username,
        password: form.password,
      };
      // Fixed: Added /api/v1 prefix to match backend routes
      return await apiClient.post(
        "/api/v1/auth/login",
        new URLSearchParams(formAsRecord),
        {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        },
      );
    } catch {
      throw new AuthError("Login failed");
    }
  },
  async register(form: RegisterFormData): Promise<AxiosResponse<User>> {
    try {
      // Fixed: Added /api/v1 prefix to match backend routes
      return await apiClient.post("/api/v1/users/open", form);
    } catch {
      throw new AuthError("Registration failed");
    }
  },
  async refreshToken(refreshToken: string): Promise<AxiosResponse<Token>> {
    try {
      const formData = new URLSearchParams();
      formData.append("refresh_token", refreshToken);
      // Fixed: Added /api/v1 prefix to match backend routes
      return await apiClient.post("/api/v1/auth/refresh", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });
    } catch {
      throw new AuthError("Token refresh failed");
    }
  },
  async logout(): Promise<AxiosResponse<void>> {
    try {
      // Fixed: Added /api/v1 prefix and removed manual Authorization header
      // The axios interceptor automatically adds the Authorization header
      return await apiClient.post("/api/v1/auth/logout", {});
    } catch {
      throw new AuthError("Logout failed");
    }
  },
  async getCurrentUser(): Promise<AxiosResponse<User>> {
    try {
      // Fixed: Added /api/v1 prefix and removed manual Authorization header
      // The axios interceptor automatically adds the Authorization header
      return await apiClient.get("/api/v1/users/me");
    } catch {
      throw new AuthError("Failed to fetch current user");
    }
  },
};
