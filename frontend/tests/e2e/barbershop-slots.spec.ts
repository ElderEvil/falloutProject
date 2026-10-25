import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

for (const width of [390, 1280]) {
  test(`barbershop worker and client slots share one picker at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    const assigned = new Set<string>()
    const moves: string[] = []
    let rejectWorker = true
    await page.route('**/static/**', (route) =>
      route.fulfill({
        path: fileURLToPath(
          new URL(
            route.request().url().includes('room_images')
              ? '../../../backend/app/static/room_images/FOS Barber 1.png'
              : '../../../backend/app/static/dweller_images/base/FOS_Dw_Default_Human_Female.webp',
            import.meta.url
          )
        ),
      })
    )
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request()
      if (request.url().includes('/dwellers/vault/'))
        return route.fulfill({
          json: ['lucy', 'cooper', 'norm', 'maximus'].map((id) => ({
            id,
            first_name: id[0].toUpperCase() + id.slice(1),
            last_name: '',
            level: 5,
            age_group: id === 'norm' ? 'child' : 'adult',
            gender: 'female',
            status: id === 'maximus' ? 'exploring' : assigned.has(id) ? 'working' : 'idle',
            health: 100,
            max_health: 100,
            room_id: assigned.has(id) ? 'barbershop-1' : null,
            thumbnail_url:
              id === 'cooper'
                ? '/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp'
                : '/static/dweller_images/base/FOS_Dw_Default_Human_Female.webp',
            is_default_portrait: true,
            visual_attributes: {
              race: id === 'cooper' ? 'ghoul' : 'human',
              skin_tone: 'Pale',
              hair_color: 'Brown',
            },
          })),
        })
      const move = request.url().match(/dwellers\/(lucy|cooper)\/move_to\/barbershop-1/)
      if (move) {
        if (move[1] === 'cooper' && rejectWorker) {
          rejectWorker = false
          return route.fulfill({ status: 409, json: { detail: 'Assignment unavailable' } })
        }
        assigned.add(move[1])
        moves.push(move[1])
        return route.fulfill({ json: { id: move[1], room_id: 'barbershop-1', status: 'working' } })
      }
      if (request.method() === 'PUT' && request.url().endsWith('/dwellers/lucy')) {
        assigned.delete('lucy')
        return route.fulfill({ json: { id: 'lucy', room_id: null, status: 'idle' } })
      }
      if (request.url().endsWith('/barbershop'))
        return route.fulfill({
          json: {
            room_id: 'barbershop-1',
            built: true,
            staffed: assigned.size > 0,
            fee: 350,
            skin_fee: 200,
            hair_fee: 150,
            vault_caps: 1000,
            skin_tones: ['Pale', 'Tan', 'Brown', 'Ebony'],
            hair_colors: ['brown', 'black', 'gray'],
          },
        })
      return route.fulfill({ json: {} })
    })
    await page.goto('/tests/e2e/fixtures/barbershop-room.html')
    const dialog = page.getByRole('dialog')
    const scene = dialog.getByRole('region', { name: 'Barbershop room preview' })
    await expect(dialog.locator('.room-preview-section')).toHaveCount(1)
    const worker = scene.getByRole('button', { name: 'Choose worker', exact: true })
    const client = scene.getByRole('button', { name: 'Choose client', exact: true })
    await expect(worker).toContainText('Add worker')
    await expect(client).toContainText('Add client')
    const silhouette = worker.locator('.empty-dweller-silhouette')
    await expect(silhouette).toHaveCSS('mask-image', /FOS_Dw_Default_Human_Male/)
    await expect(worker).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    await expect(worker).toHaveCSS('border-top-width', '0px')
    const idleColor = await silhouette.evaluate((node) => getComputedStyle(node).backgroundColor)
    await worker.hover()
    await expect
      .poll(() => silhouette.evaluate((node) => getComputedStyle(node).backgroundColor))
      .not.toBe(idleColor)
    await client.click()
    const clientPicker = dialog.getByRole('region', { name: 'Choose client' })
    await expect(clientPicker.getByRole('searchbox')).toBeFocused()
    await expect(clientPicker.getByRole('button', { name: /Cooper|Norm|Maximus/ })).toHaveCount(0)
    await clientPicker.getByRole('button', { name: /Lucy/ }).click()
    await expect(clientPicker).toBeHidden()
    await expect(client).toBeFocused()
    await expect(worker).toContainText('Add worker')
    expect(moves).toEqual(['lucy'])

    await worker.click()
    const workerPicker = dialog.getByRole('region', { name: 'Choose worker' })
    await workerPicker.getByRole('searchbox').fill('Cooper')
    await workerPicker.getByRole('button', { name: /Cooper/ }).click()
    await expect(dialog.getByRole('alert')).toContainText('Assignment unavailable')
    await expect(worker).toContainText('Add worker')
    await expect(workerPicker).toBeVisible()
    await workerPicker.getByRole('button', { name: /Cooper/ }).click()
    await expect(workerPicker).toBeHidden()
    await expect(scene).toContainText('Cooper')
    await expect(scene).toContainText('Lucy')
    expect(moves).toEqual(['lucy', 'cooper'])
    const portrait = (await worker.boundingBox())!
    const controls = (await scene
      .getByRole('group', { name: 'Controls for Worker' })
      .boundingBox())!
    expect(controls.y).toBeGreaterThanOrEqual(portrait.y + portrait.height)
    await page.screenshot({ path: testInfo.outputPath(`barbershop-${width}.png`), fullPage: true })
    expect(
      await dialog
        .locator('.barbershop-panel')
        .evaluate((node) => node.scrollWidth <= node.clientWidth)
    ).toBe(true)

    await scene.getByRole('button', { name: 'Unassign Lucy from Barbershop' }).click()
    await expect(client).toContainText('Add client')
    await expect(client).toBeFocused()
    await expect(worker).not.toContainText('Add worker')
    await client.click()
    await clientPicker.getByRole('searchbox').press('Escape')
    await expect(clientPicker).toBeHidden()
    await expect(client).toBeFocused()
  })
}
