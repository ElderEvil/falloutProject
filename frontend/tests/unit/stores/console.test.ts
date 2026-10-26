import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useConsoleStore } from '@/modules/console/stores/console'
import { parseCommand, completeCommand } from '@/modules/console/utils/commands'
import type { ConsoleManifest } from '@/modules/console/api/consoleApi'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const manifest: ConsoleManifest = {
  commands: [
    {
      name: 'help',
      description: 'Help',
      mutates: false,
      args_schema: { properties: { command: { type: 'string' } } },
    },
    {
      name: 'expedition.status',
      description: 'Status',
      mutates: false,
      args_schema: { properties: { vault_id: { type: 'string' } } },
    },
    {
      name: 'expedition.setup',
      description: 'Setup',
      mutates: true,
      args_schema: {
        properties: {
          vault_id: { type: 'string' },
          dweller_id: { type: 'string' },
          site_id: { type: 'string' },
          duration_hours: { type: 'integer' },
        },
      },
    },
  ],
  sites: [],
}

function admin(id = 'admin-one'): void {
  const auth = useAuthStore()
  auth.token = 'test'
  auth.user = {
    id,
    username: 'Overseer',
    email: 'admin@example.com',
    is_active: true,
    is_superuser: true,
    email_verified: true,
    has_password: true,
    created_at: '2026-10-26T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z',
  }
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.resetAllMocks()
  vi.mocked(apiClient.get).mockResolvedValue({ data: manifest })
})

describe('console commands', () => {
  it('parses named arguments and inherits vault context only when omitted', () => {
    expect(
      parseCommand(
        'expedition.setup --dweller-id dweller --site-id collapsed_subway --duration-hours 8',
        manifest,
        'vault'
      ).args
    ).toEqual({
      vault_id: 'vault',
      dweller_id: 'dweller',
      site_id: 'collapsed_subway',
      duration_hours: 8,
    })
    expect(parseCommand('expedition.status --vault-id another', manifest, 'vault').args).toEqual({
      vault_id: 'another',
    })
    expect(parseCommand('help expedition.setup', manifest)).toEqual({
      command: 'help',
      args: { command: 'expedition.setup' },
    })
  })

  it.each([
    'expedition.status --vault-id',
    'expedition.status --shell sh',
    'expedition.status --vault-id a --vault-id b',
    'sh -c whoami',
  ])('rejects malformed or unregistered input: %s', (input) => {
    expect(() => parseCommand(input, manifest)).toThrow()
  })

  it('completes commands and arguments from the server manifest', () => {
    expect(completeCommand('exp', manifest)).toEqual(['expedition.status', 'expedition.setup'])
    expect(completeCommand('expedition.setup --site', manifest)).toEqual([
      'expedition.setup --site-id',
    ])
  })
})

describe('console session ownership', () => {
  it('does not fetch or execute for ordinary users', async () => {
    const terminal = useConsoleStore()
    await terminal.show()
    await terminal.execute('help')
    expect(apiClient.get).not.toHaveBeenCalled()
    expect(apiClient.post).not.toHaveBeenCalled()
  })

  it('loads manifest once and shows handled command errors', async () => {
    admin()
    const terminal = useConsoleStore()
    await terminal.show()
    await terminal.show()
    expect(apiClient.get).toHaveBeenCalledTimes(1)
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { ok: false, lines: ['Dweller is already exploring'] },
    })
    await terminal.execute('expedition.status', 'vault')
    expect(terminal.lines.at(-1)).toEqual({ text: 'Dweller is already exploring', kind: 'error' })
    expect(terminal.history).toEqual(['expedition.status'])
  })

  it('ignores a slow manifest response after logout', async () => {
    admin()
    let resolve!: (result: { data: ConsoleManifest }) => void
    vi.mocked(apiClient.get).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        })
    )
    const terminal = useConsoleStore()
    const loading = terminal.show()
    useAuthStore().token = null
    resolve({ data: manifest })
    await loading
    expect(terminal.open).toBe(false)
    expect(terminal.manifest).toBeNull()
    expect(terminal.lines).toEqual([])
  })

  it.each(['account', 'vault'])('drops delayed results after a %s switch', async (scope) => {
    admin()
    const terminal = useConsoleStore()
    await terminal.show()
    let resolve!: (value: unknown) => void
    vi.mocked(apiClient.post).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        })
    )
    const pending = terminal.execute('expedition.status', 'old-vault')
    if (scope === 'account') admin('admin-two')
    else terminal.reset()
    resolve({ data: { ok: true, lines: ['Old account or vault result'] } })
    await pending
    expect(terminal.lines).toEqual([])
    expect(terminal.busy).toBe(false)
  })

  it('bounds scrollback and command history', async () => {
    admin()
    const terminal = useConsoleStore()
    await terminal.show()
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { ok: true, lines: Array.from({ length: 600 }, (_, i) => String(i)) },
    })
    await terminal.execute('help')
    expect(terminal.lines).toHaveLength(500)
    expect(terminal.lines[0]?.text).toBe('100')
    terminal.history = Array.from({ length: 100 }, (_, i) => `help ${i}`)
    await terminal.execute('help expedition.status')
    expect(terminal.history).toHaveLength(100)
    expect(terminal.history.at(-1)).toBe('help expedition.status')
  })
})
