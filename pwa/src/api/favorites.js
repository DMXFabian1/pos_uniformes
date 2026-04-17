import { api } from './client'

export const favoritesApi = {
  /** Devuelve { product_keys: string[] } */
  list: () => api.get('/api/v1/favorites'),

  /** Alterna el favorito; devuelve { product_key, active } */
  toggle: (productKey) =>
    api.post('/api/v1/favorites/toggle', { product_key: productKey }),
}
