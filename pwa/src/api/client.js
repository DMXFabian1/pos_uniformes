/**
 * Cliente HTTP base para la API del POS.
 * Lee el token de sessionStorage y lo adjunta en cada request.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

function getToken() {
  return sessionStorage.getItem('pos_token') ?? localStorage.getItem('pos_token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 204) return null

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    const message = data?.error?.message ?? `Error ${res.status}`
    const code = data?.error?.code ?? 'error_desconocido'
    const err = new Error(message)
    err.code = code
    err.status = res.status
    throw err
  }

  return data
}

export const api = {
  get:    (path, opts) => request(path, { method: 'GET', ...opts }),
  post:   (path, body, opts) => request(path, { method: 'POST', body: JSON.stringify(body), ...opts }),
  put:    (path, body, opts) => request(path, { method: 'PUT', body: JSON.stringify(body), ...opts }),
  delete: (path, opts) => request(path, { method: 'DELETE', ...opts }),
}
