const base = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
let accessToken = null
export function setAccessToken(token) { accessToken = token }
export function query(values = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== null && value !== '') params.set(key, value)
  return params.size ? `?${params}` : ''
}
export async function request(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  let response
  try {
    response = await fetch(base + path, {
      method, credentials: 'include',
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch { throw Object.assign(new Error('Сервер недоступен. Проверьте запуск FastAPI и подключение к сети.'), { code: 'NETWORK' }) }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw Object.assign(new Error(data.message || 'Не удалось выполнить запрос.'), { code: data.code || 'HTTP_ERROR', status: response.status })
  }
  if (raw) return response
  return response.status === 204 ? null : response.json()
}
export async function allPages(path, filters = {}) {
  const items = []
  let offset = 0
  while (true) {
    const page = await request(path + query({ ...filters, offset, limit: 100 }))
    items.push(...page.items)
    if (!page.items.length || items.length >= page.total) break
    offset += page.items.length
  }
  return items
}
