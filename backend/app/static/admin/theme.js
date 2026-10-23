(() => {
  const key = 'vault-admin-theme'
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  let preference = 'dark'
  try {
    const saved = localStorage.getItem(key)
    if (['dark', 'light', 'system'].includes(saved)) preference = saved
  } catch {}
  const apply = () => {
    document.documentElement.dataset.bsTheme = preference === 'system'
      ? (media.matches ? 'dark' : 'light') : preference
  }
  apply()
  media.addEventListener('change', apply)
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('admin-theme')
    if (!select) return
    select.value = preference
    select.addEventListener('change', () => {
      preference = select.value
      apply()
      try { localStorage.setItem(key, preference) } catch {}
    })
  })
})()
