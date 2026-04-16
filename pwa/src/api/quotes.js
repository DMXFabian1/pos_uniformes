import { api } from './client'

export const quotesApi = {
  list: () => api.get('/api/v1/quotes'),

  get: (id) => api.get(`/api/v1/quotes/${id}`),

  create: (body) => api.post('/api/v1/quotes', body),

  update: (id, body) => api.put(`/api/v1/quotes/${id}`, body),

  markReady: (id) => api.post(`/api/v1/quotes/${id}/ready`),

  cancel: (id) => api.delete(`/api/v1/quotes/${id}`),
}
