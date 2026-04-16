import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { quotesApi } from '../api/quotes'
import { useCart } from '../context/CartContext'
import Spinner from '../components/Spinner'

export default function QuotesScreen() {
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(true)
  const { lines }             = useCart()
  const navigate              = useNavigate()

  useEffect(() => {
    quotesApi.list()
      .then(setQuotes)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function markReady(id, e) {
    e.stopPropagation()
    await quotesApi.markReady(id)
    setQuotes(q => q.filter(p => p.id !== id))
  }

  async function cancel(id, e) {
    e.stopPropagation()
    if (!confirm('¿Cancelar este presupuesto?')) return
    await quotesApi.cancel(id)
    setQuotes(q => q.filter(p => p.id !== id))
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <h2 className="font-bold text-gray-900 text-lg">Mis presupuestos</h2>
        <p className="text-xs text-gray-400">Borradores activos en el servidor</p>
      </div>

      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2">
        {/* Presupuesto local en construccion */}
        {lines.length > 0 && (
          <button
            onClick={() => navigate('/quotes/current')}
            className="w-full bg-brand-700 text-white rounded-2xl p-4 text-left"
          >
            <p className="font-semibold">Presupuesto en curso</p>
            <p className="text-sm text-white/70">{lines.length} producto{lines.length !== 1 ? 's' : ''} — toca para continuar</p>
          </button>
        )}

        {loading && <Spinner className="py-12" />}

        {!loading && quotes.length === 0 && lines.length === 0 && (
          <div className="text-center py-12">
            <p className="text-4xl mb-3">📋</p>
            <p className="text-gray-500 font-medium">Sin borradores activos</p>
            <p className="text-sm text-gray-400 mt-1">Empieza uno desde el catálogo</p>
          </div>
        )}

        {!loading && quotes.map(q => (
          <div key={q.id} className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-semibold text-gray-900 text-sm">{q.folio}</p>
                {q.cliente_nombre && <p className="text-xs text-gray-500">Cliente: {q.cliente_nombre}</p>}
                <p className="text-xs text-gray-400">{q.total_lineas} línea{q.total_lineas !== 1 ? 's' : ''}</p>
              </div>
              <p className="font-bold text-brand-700">
                ${Number(q.total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={(e) => markReady(q.id, e)}
                className="flex-1 bg-green-600 text-white text-sm font-semibold py-2 rounded-xl active:bg-green-700"
              >
                Listo para caja ✓
              </button>
              <button
                onClick={(e) => cancel(q.id, e)}
                className="px-4 bg-gray-100 text-gray-600 text-sm font-medium py-2 rounded-xl active:bg-gray-200"
              >
                Cancelar
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
