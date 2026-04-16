import { api } from './client'

export const authApi = {
  getEmployees: () => api.get('/api/v1/auth/employees'),

  login: (employee_id, pin, device_id) =>
    api.post('/api/v1/auth/login', { employee_id, pin, device_id }),

  logout: () => api.post('/api/v1/auth/logout'),

  me: () => api.get('/api/v1/auth/me'),

  health: () => api.get('/health'),
}
