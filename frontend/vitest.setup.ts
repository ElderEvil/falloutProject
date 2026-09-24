// Mock localStorage for jsdom environment
import { beforeEach } from 'vitest'
import apiClient from '@/core/plugins/axios'

// Never let tests hit the network: jsdom XHRs settle on macrotasks and can
// outlive the test file, crashing the vitest worker with
// EnvironmentTeardownError ("Closing rpc while onUserConsoleLog was pending")
// when fire-and-forget calls (e.g. the auth store's init fetchUser) log later.
// Rejecting in a microtask lets those chains settle before teardown.
apiClient.defaults.adapter = () => Promise.reject(new Error('Network requests are stubbed in unit tests'))

const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    key: (index: number) => {
      const keys = Object.keys(store)
      return keys[index] || null
    },
    get length() {
      return Object.keys(store).length
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock sessionStorage similarly
const sessionStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    key: (index: number) => {
      const keys = Object.keys(store)
      return keys[index] || null
    },
    get length() {
      return Object.keys(store).length
    },
  }
})()

Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
})

// Stale auth tokens in storage make useAuthStore() fire a real fetchUser() on
// creation in a later test; the pending network rejection outlives the file and
// crashes the vitest worker (EnvironmentTeardownError). Start each test clean.
beforeEach(() => {
  localStorageMock.clear()
  sessionStorageMock.clear()
})

// jsdom 29 lacks the Pointer Capture API, which reka-ui's Select/Popover pointer
// handlers call during pointerdown. Provide no-op implementations so interactions
// can be driven with synthetic pointer events.
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {}
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {}
}
if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false
}

// jsdom lacks ResizeObserver, which reka-ui's Slider (useSize) constructs on mount.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}
