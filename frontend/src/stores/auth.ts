import { computed } from "vue";
import { defineStore } from "pinia";
import { useLocalStorage } from "@vueuse/core";
import axios from "@/plugins/axios";
import type { User } from "@/types/user";

export const useAuthStore = defineStore("auth", () => {
  // State (using VueUse for reactive localStorage)
  const token = useLocalStorage<string | null>("token", null);
  const refreshToken = useLocalStorage<string | null>("refreshToken", null);
  const user = useLocalStorage<User | null>("user", null, {
    serializer: {
      read: (v: string) => {
        try {
          return JSON.parse(v);
        } catch {
          return null;
        }
      },
      write: (v: User | null) => JSON.stringify(v),
    },
  });

  // Getters
  const isAuthenticated = computed(() => !!token.value);
  const isSuperuser = computed(() => user.value?.is_superuser ?? false);

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const formData = new URLSearchParams();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post("/api/v1/auth/login", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      token.value = response.data.access_token;
      refreshToken.value = response.data.refresh_token;

      if (!token.value || !refreshToken.value) {
        return false;
      }

      await fetchUser();
      return true;
    } catch (error) {
      console.error("Login failed", error);
      return false;
    }
  }

  async function register(
    username: string,
    email: string,
    password: string,
  ): Promise<boolean> {
    try {
      const response = await axios.post("/api/v1/users/open", {
        username,
        email,
        password,
      });

      token.value = response.data.access_token;
      refreshToken.value = response.data.refresh_token;

      if (!token.value || !refreshToken.value) {
        return false;
      }

      await fetchUser();
      return true;
    } catch (error) {
      console.error("Registration failed", error);
      return false;
    }
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return;

    try {
      // No need to manually set Authorization header - axios interceptor handles it
      const response = await axios.get("/api/v1/users/me");
      user.value = response.data;
    } catch (error) {
      console.error("Failed to fetch user", error);
      await logout();
    }
  }

  async function refreshAccessToken(): Promise<void> {
    if (!refreshToken.value) return;

    try {
      const formData = new URLSearchParams();
      formData.append("refresh_token", refreshToken.value);

      const response = await axios.post("/api/v1/auth/refresh", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      token.value = response.data.access_token;
    } catch (error) {
      console.error("Failed to refresh token", error);
      await logout();
    }
  }

  async function logout(): Promise<void> {
    try {
      if (token.value) {
        // No need to manually set Authorization header - axios interceptor handles it
        await axios.post("/api/v1/auth/logout", {});
      }
    } catch (error) {
      console.error("Logout failed", error);
    } finally {
      // Clear all stored data (VueUse handles localStorage automatically)
      token.value = null;
      refreshToken.value = null;
      user.value = null;
    }
  }

  // Initialize: fetch user if we have a token but no user data
  if (token.value && !user.value) {
    fetchUser();
  }

  return {
    // State
    token,
    refreshToken,
    user,
    // Getters
    isAuthenticated,
    isSuperuser,
    // Actions
    login,
    register,
    fetchUser,
    refreshAccessToken,
    logout,
  };
});
