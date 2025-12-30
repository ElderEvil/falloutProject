import { defineStore } from 'pinia'

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  details?: string
  duration?: number
}

export const useNotificationStore = defineStore('notification', {
  state: () => ({
    notifications: [] as Notification[]
  }),
  actions: {
    add(notification: Omit<Notification, 'id'>) {
      const id = Date.now().toString() + Math.random().toString(36).substring(2, 9)
      const newNotification: Notification = {
        id,
        duration: 5000,
        ...notification
      }

      this.notifications.push(newNotification)

      // Auto remove after duration
      if (newNotification.duration && newNotification.duration > 0) {
        setTimeout(() => {
          this.remove(id)
        }, newNotification.duration)
      }

      return id
    },
    remove(id: string) {
      const index = this.notifications.findIndex(n => n.id === id)
      if (index > -1) {
        this.notifications.splice(index, 1)
      }
    },
    success(title: string, message: string, details?: string) {
      return this.add({ type: 'success', title, message, details })
    },
    error(title: string, message: string, details?: string) {
      return this.add({ type: 'error', title, message, details, duration: 8000 })
    },
    warning(title: string, message: string, details?: string) {
      return this.add({ type: 'warning', title, message, details })
    },
    info(title: string, message: string, details?: string) {
      return this.add({ type: 'info', title, message, details })
    },
    clear() {
      this.notifications = []
    }
  }
})
