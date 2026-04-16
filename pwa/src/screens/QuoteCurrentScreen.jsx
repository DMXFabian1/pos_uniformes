/**
 * Presupuesto activo en construccion (carrito local).
 * Al confirmar, lo guarda en el servidor y limpia el carrito.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { quotesApi } from '../api/quotes'

export default function QuoteCurrentScreen() {
  const { lines, client, total, updateQty, removeLine, clear } = useCart()
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')
  const navigate            = useNavigate()

  if (lines.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6">
        <p className="text-5xl mb-4">📋</p>
        <p className="font-semibold text-gray-700 mb-2">El presupuesto está vacío</p>
        <p className="text-sm text-gray-400 mb-6">Agrega productos desde el catálogo</p>
        <button onClick={() => navigate('/catalog')} className="bg-brand-700 text-white px-6 py-3 rounded-xl font-semibold">
          Ir al catálogo
        </button>
      </div>
    )
  }

  async function saveAndSend() {
    setSaving(true)
    setError('')
    try {
      await quotesApi.create({
        cliente_id: client?.id ?? null,
        cliente_nombre: client?.nombre ?? null,
        lineas: lines.map(l => ({
          sku: l.sku,
          cantidad: l.cantidad,
          precio_unitario: l.precio,
        })),
      })
      clear()
      navigate('/quotes', { replace: true })
    } catch (e) {
      setError(e.message ?? 'No se pudo guardar el presupuesto.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-bold text-gray-900">Presupuesto actual</h2>
            {client && <p className="text-sm text-gray-500">Cliente: {client.nombre}</p>}
          </div>
          <button
            onClick={() => { if (confirm('¿Limpiar el presupuesto?')) clear() }}
            className="text-red-400 text-sm"
          >
            Limpiar
          </button>
        </div>
      </div>

      {/* Lineas */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2">
        {lines.map(l => (
          <div key={l.sku} className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 text-sm leading-snug">{l.descripcion}</p>
                <p className="text-xs text-gray-400 mt-0.5">{l.sku}</p>
              </div>
              <button onClick={() => removeLine(l.sku)} className="text-gray-300 active:text-red-400 text-xl shrink-0">×</button>
            </div>
            <div className="flex items-center justify-between">
              {/* Contador */}
              <div className="flex items-center gap-3 bg-gray-100 rounded-xl px-3 py-1.5">
                <button onClick={() => updateQty(l.sku, l.cantidad - 1)} className="text-gray-600 text-xl w-6 h-6 flex items-center justify-center">−</button>
                <span className="font-semibold text-gray-900 w-5 text-center">{l.cantidad}</span>
                <button onClick={() => updateQty(l.sku, l.cantidad + 1)} className="text-gray-600 text-xl w-6 h-6 flex items-center justify-center">+</button>
              </div>
              {/* Precio */}
              <div className="text-right">
                <p className="text-xs text-gray-400">${Number(l.precio).toFixed(2)} c/u</p>
                <p className="font-bold text-brand-700">
                  ${Number(l.subtotal).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="bg-white border-t border-gray-100 px-4 py-4 space-y-3">
        {error && <p className="text-red-600 text-sm text-center">{error}</p>}

        <div className="flex justify-between items-center">
          <span className="text-gray-600 font-medium">Total</span>
          <span className="text-2xl font-bold text-brand-700">
            ${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
          </span>
        </div>

        <button
          onClick={saveAndSend}
          disabled={saving}
          className="w-full bg-brand-700 text-white font-bold py-4 rounded-2xl text-lg active:bg-brand-800 disabled:opacity-50 shadow-lg"
        >
          {saving ? 'Guardando…' : 'Guardar presupuesto'}
        </button>

        <button
          onClick={() => navigate('/catalog')}
          className="w-full text-brand-600 font-medium py-2 text-sm"
        >
          + Agregar más productos
        </button>
      </div>
    </div>
  )
}
