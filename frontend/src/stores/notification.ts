import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useTimeoutFn } from '@vueuse/core'

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  details?: string;
  duration?: number;
}

export const useNotificationStore = defineStore('notification', () => {
  // State
  const notifications = ref<Notification[]>([]);

  // Actions
  function add(notification: Omit<Notification, 'id'>): string {
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 9);
    const newNotification: Notification = {
      id,
      duration: 5000,
      ...notification
    };

    notifications.value.push(newNotification);

    // Auto remove after duration using VueUse's useTimeoutFn
    if (newNotification.duration && newNotification.duration > 0) {
      useTimeoutFn(() => {
        remove(id);
      }, newNotification.duration);
    }

    return id;
  }

  function remove(id: string): void {
    const index = notifications.value.findIndex((n) => n.id === id);
    if (index > -1) {
      notifications.value.splice(index, 1);
    }
  }

  function success(title: string, message: string, details?: string): string {
    return add({ type: 'success', title, message, details });
  }

  function error(title: string, message: string, details?: string): string {
    return add({ type: 'error', title, message, details, duration: 8000 });
  }

  function warning(title: string, message: string, details?: string): string {
    return add({ type: 'warning', title, message, details });
  }

  function info(title: string, message: string, details?: string): string {
    return add({ type: 'info', title, message, details });
  }

  function clear(): void {
    notifications.value = [];
  }

  return {
    // State
    notifications,
    // Actions
    add,
    remove,
    success,
    error,
    warning,
    info,
    clear
  };
});
