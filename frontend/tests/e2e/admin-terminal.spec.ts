import { expect, test } from '@playwright/test'

const manifest = {
  commands: [
    {
      name: 'greedisgood',
      description: 'Grant caps',
      mutates: true,
      args_schema: { properties: { vault_id: { type: 'string' }, amount: { type: 'integer' } } },
    },
    {
      name: 'help',
      description: 'Help',
      mutates: false,
      args_schema: { properties: { command: { type: 'string' } } },
    },
    {
      name: 'vault.state',
      description: 'State',
      mutates: false,
      args_schema: { properties: { vault_id: { type: 'string' } } },
    },
    {
      name: 'expedition.status',
      description: 'Status',
      mutates: false,
      args_schema: { properties: { vault_id: { type: 'string' } } },
    },
  ],
  sites: [{ id: 'collapsed_subway', name: 'Collapsed Subway', min_level: 1 }],
}

for (const width of [390, 1440]) {
  test(`admin terminal keyboard, history and context at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    let manifestRequests = 0
    const commands: unknown[] = []
    await page.route('**/api/v1/system/console/manifest', (route) => {
      manifestRequests++
      return route.fulfill({ json: manifest })
    })
    await page.route('**/api/v1/system/console', (route) => {
      const command = route.request().postDataJSON()
      commands.push(command)
      if (command.command === 'greedisgood') {
        return route.fulfill({
          json: { ok: true, lines: ['Greed is good! +500 caps.'], links: [] },
        })
      }
      return route.fulfill({
        json: {
          ok: true,
          lines: ['Moldaver — Collapsed Subway available'],
          links: [
            {
              label: 'Open site',
              to: '/vault/92d378b7-3835-43bd-84e3-dc005ef4d44b/exploration/test?siteId=collapsed_subway',
            },
          ],
        },
      })
    })
    await page.goto('/tests/e2e/fixtures/admin-terminal.html')
    await page.getByLabel('Bio').focus()
    await page.keyboard.press('Backquote')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect(manifestRequests).toBe(0)
    await page.getByLabel('Bio').blur()
    await page.keyboard.press('Backquote')
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const input = page.getByRole('textbox', { name: 'Admin command' })
    await expect(input).toBeFocused()
    await input.fill('exp')
    await input.press('Tab')
    await expect(input).toHaveValue('expedition.status')
    await input.press('Enter')
    await expect(page.getByRole('log')).toContainText('Collapsed Subway available')
    expect(commands).toEqual([
      { command: 'expedition.status', args: { vault_id: '92d378b7-3835-43bd-84e3-dc005ef4d44b' } },
    ])
    await input.press('ArrowUp')
    await expect(input).toHaveValue('expedition.status')
    await input.press('ArrowDown')
    await expect(input).toHaveValue('')
    await input.fill('greedisgood --amount 500')
    await input.press('Enter')
    await expect.poll(() => commands.length).toBe(2)
    expect(commands[1]).toEqual({
      command: 'greedisgood',
      args: { amount: 500, vault_id: '92d378b7-3835-43bd-84e3-dc005ef4d44b' },
    })
    await input.press('Escape')
    await expect(dialog).toHaveCount(0)
    await page.getByRole('button', { name: 'Open admin terminal' }).click()
    await expect(dialog).toBeVisible()
    expect(manifestRequests).toBe(1)
    const box = await dialog.boundingBox()
    expect(box!.y).toBeLessThan(2)
    expect(box!.width).toBeLessThanOrEqual(width)
    await page.getByRole('link', { name: 'Open site' }).click()
    await expect(dialog).toHaveCount(0)
  })
}
