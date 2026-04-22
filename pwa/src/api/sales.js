import { api } from './client'

export const salesApi = {
  today: () => api.get('/api/v1/sales/today'),

  list: ({ desde, hasta, page = 1, pageSize = 30 } = {}) => {
    const params = new URLSearchParams({ page, page_size: pageSize })
    if (desde) params.set('desde', desde)
    if (hasta) params.set('hasta', hasta)
    return api.get(`/api/v1/sales?${params}`)
  },

  get: (id) => api.get(`/api/v1/sales/${id}`),
}
