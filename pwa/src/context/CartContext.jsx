/**
 * Carrito local para el presupuesto en construccion.
 * Al crear/guardar el presupuesto en el servidor se limpia.
 */
import { createContext, useContext, useState, useCallback } from 'react'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  const [lines, setLines] = useState([])
  const [client, setClient] = useState(null)   // { id, nombre, codigo_cliente }
  const [quoteId, setQuoteId] = useState(null) // ID del borrador en el servidor

  const addLine = useCallback((variante, producto) => {
    setLines(prev => {
      const existing = prev.find(l => l.sku === variante.sku)
      if (existing) {
        return prev.map(l =>
          l.sku === variante.sku
            ? { ...l, cantidad: l.cantidad + 1, subtotal: l.precio * (l.cantidad + 1) }
            : l
        )
      }
      return [...prev, {
        sku: variante.sku,
        descripcion: `${producto.nombre} ${variante.talla} ${variante.color}`.trim(),
        talla: variante.talla,
        color: variante.color,
        precio: variante.precio_venta,
        cantidad: 1,
        subtotal: variante.precio_venta,
      }]
    })
  }, [])

  const removeLine = useCallback((sku) => {
    setLines(prev => prev.filter(l => l.sku !== sku))
  }, [])

  const updateQty = useCallback((sku, cantidad) => {
    if (cantidad <= 0) {
      setLines(prev => prev.filter(l => l.sku !== sku))
      return
    }
    setLines(prev => prev.map(l =>
      l.sku === sku ? { ...l, cantidad, subtotal: l.precio * cantidad } : l
    ))
  }, [])

  const clear = useCallback(() => {
    setLines([])
    setClient(null)
    setQuoteId(null)
  }, [])

  const total = lines.reduce((acc, l) => acc + Number(l.subtotal), 0)

  return (
    <CartContext.Provider value={{
      lines, client, quoteId, total,
      setClient, setQuoteId,
      addLine, removeLine, updateQty, clear,
    }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  return useContext(CartContext)
}
