import { api } from './client'

export const clientsApi = {
  byQr: (codigo) => api.get(`/api/v1/clients/by-qr/${encodeURIComponent(codigo)}`),
}
