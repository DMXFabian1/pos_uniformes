import { api } from './client'

export const catalogApi = {
  list: (q = '', page = 1, pageSize = 30) => {
    const params = new URLSearchParams({ page, page_size: pageSize })
    if (q) params.set('q', q)
    return api.get(`/api/v1/catalog?${params}`)
  },

  get: (id) => api.get(`/api/v1/catalog/${id}`),

  bySku: (sku) => api.get(`/api/v1/catalog/sku/${encodeURIComponent(sku)}`),
}
