import { config } from '@vue/test-utils';
import { vi } from 'vitest';

// Mock Naive UI components globally
config.global.stubs = {
  'n-button': true,
  'n-form': true,
  'n-form-item': true,
  'n-input': true,
  'n-card': true,
  'n-space': true,
  'n-tabs': true,
  'n-tab-pane': true,
  'n-modal': true,
  'n-progress': true,
  'n-message-provider': true,
  'n-config-provider': true,
  'n-grid': true,
  'n-gi': true,
  'n-dropdown': true,
  'n-select': true,
  'n-scrollbar': true,
  'n-popconfirm': true
};

// Mock vue-draggable
vi.mock('vuedraggable', () => ({
  default: {
    name: 'draggable',
    props: ['modelValue'],
    template: '<div><slot></slot></div>'
  }
}));

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn()
  }),
  useRoute: () => ({
    params: {},
    query: {}
  })
}));

// Mock window.crypto for UUID generation
Object.defineProperty(window, 'crypto', {
  value: {
    randomUUID: () => '123e4567-e89b-12d3-a456-426614174000'
  }
});
