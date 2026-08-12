import { readFileSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

// Boundary checks are release gates. `--warn` remains available for local
// exploration, but CI intentionally uses the default hard-fail mode.
const strict = !process.argv.includes('--warn')

function collectFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectFiles(path)
    return /\.(ts|vue)$/.test(entry.name) ? [path] : []
  })
}

function scriptContent(source, fileName) {
  if (!fileName.endsWith('.vue')) return source
  return [...source.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map((match) => match[1])
    .join('\n')
}

export function collectModuleSpecifiers(source, fileName = 'source.ts') {
  const sourceFile = ts.createSourceFile(
    fileName,
    scriptContent(source, fileName),
    ts.ScriptTarget.Latest,
    true
  )
  const specifiers = new Set()

  const visit = (node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specifiers.add(node.moduleSpecifier.text)
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      specifiers.add(node.arguments[0].text)
    }
    ts.forEachChild(node, visit)
  }

  visit(sourceFile)
  return [...specifiers]
}

export function hasModuleDependency(source, fileName) {
  return collectModuleSpecifiers(source, fileName).some((specifier) =>
    specifier.startsWith('@/modules/')
  )
}

export function findViolations(files, allowlist = new Set(), cwd = process.cwd()) {
  return files.flatMap((file) => {
    const relativePath = relative(cwd, file)
    if (allowlist.has(relativePath)) return []
    return hasModuleDependency(readFileSync(file, 'utf8'), file) ? [relativePath] : []
  })
}

const isMainModule =
  import.meta.url.startsWith('file:') &&
  process.argv[1] &&
  fileURLToPath(import.meta.url) === process.argv[1]

if (isMainModule) {
  const rootPath = fileURLToPath(new URL('../src/core/', import.meta.url))
  const allowlistUrl = new URL('./boundary-allowlist.json', import.meta.url)
  const allowlist = new Set(JSON.parse(readFileSync(allowlistUrl, 'utf8')))
  const violations = findViolations(collectFiles(rootPath), allowlist)

  if (violations.length === 0) {
    console.log('Module boundary check: no core → module imports found.')
  } else {
    const mode = strict ? 'error' : 'warning'
    console[mode === 'error' ? 'error' : 'warn'](
      `Module boundary check (${mode}):\n${violations.map((file) => `- ${file}`).join('\n')}`
    )
  }

  if (strict && violations.length > 0) process.exitCode = 1
}
