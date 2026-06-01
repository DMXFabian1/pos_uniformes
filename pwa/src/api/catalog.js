import { api } from './client'

export const catalogApi = {
  list: (q = '', page = 1, pageSize = 30) => {
    const params = new URLSearchParams({ page, page_size: pageSize })
    if (q) params.set('q', q)
    return api.get(`/api/v1/catalog?${params}`)
  },

  get: (id) => api.get(`/api/v1/catalog/${id}`),

  bySku: (sku) => api.get(`/api/v1/catalog/sku/${encodeURIComponent(sku)}`),

  guidedOptions: () => api.get('/api/v1/catalog/guided/options'),

  guidedProducts: ({ mode, escuela_id, tipo_prenda, genero, tipo_pieza_id } = {}) => {
    const params = new URLSearchParams({ mode })
    if (escuela_id   != null) params.set('escuela_id',   escuela_id)
    if (tipo_prenda  != null) params.set('tipo_prenda',  tipo_prenda)
    if (genero       != null) params.set('genero',       genero)
    if (tipo_pieza_id != null) params.set('tipo_pieza_id', tipo_pieza_id)
    return api.get(`/api/v1/catalog/guided/products?${params}`)
  },

  quickSearch: (q, { mode, limit } = {}) => {
    const params = new URLSearchParams({ q })
    if (mode)  params.set('mode', mode)
    if (limit) params.set('limit', limit)
    return api.get(`/api/v1/search?${params}`)
  },
}
