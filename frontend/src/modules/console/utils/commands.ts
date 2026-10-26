import type { ConsoleManifest, ConsoleRequest } from '../api/consoleApi'

export function parseCommand(
  input: string,
  manifest: ConsoleManifest,
  vaultId?: string
): ConsoleRequest {
  const [command = '', ...tokens] = input.trim().split(/\s+/)
  const spec = manifest.commands.find((item) => item.name === command)
  if (!spec) throw new Error(`Unknown command: ${command}. Use help to list commands.`)
  if (command === 'help' && tokens.length === 1 && !tokens[0]!.startsWith('--')) {
    return { command, args: { command: tokens[0] } }
  }
  const properties = (spec.args_schema.properties ?? {}) as Record<string, { type?: string }>
  const args: Record<string, unknown> = {}
  for (let i = 0; i < tokens.length; i += 2) {
    const option = tokens[i]!
    const key = option.slice(2).replaceAll('-', '_')
    const value = tokens[i + 1]
    if (!option.startsWith('--') || !Object.hasOwn(properties, key)) {
      throw new Error(`Unknown argument: ${option}. Try help ${command}.`)
    }
    if (value === undefined || value.startsWith('--'))
      throw new Error(`Missing value for ${option}.`)
    if (Object.hasOwn(args, key)) throw new Error(`Repeated argument: ${option}.`)
    args[key] = properties[key]?.type === 'integer' ? Number(value) : value
  }
  if (vaultId && Object.hasOwn(properties, 'vault_id') && !args.vault_id) args.vault_id = vaultId
  return { command, args }
}

export function completeCommand(input: string, manifest: ConsoleManifest): string[] {
  if (!input.includes(' '))
    return manifest.commands.map((c) => c.name).filter((name) => name.startsWith(input))
  const parts = input.split(/\s+/)
  const spec = manifest.commands.find((c) => c.name === parts[0])
  const prefix = parts.pop() ?? ''
  const options = Object.keys(spec?.args_schema.properties ?? {}).map(
    (key) => `--${key.replaceAll('_', '-')}`
  )
  return options
    .filter((option) => option.startsWith(prefix))
    .map((option) => [...parts, option].join(' '))
}
