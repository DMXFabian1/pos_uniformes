import { useState, useEffect } from 'react'
import { salesApi } from '../api/sales'
import Spinner from '../components/Spinner'

export default function SalesScreen() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    salesApi.today()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner className="py-12" />

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <h2 className="font-bold text-gray-900 text-lg">Mis ventas de hoy</h2>
        <p className="text-xs text-gray-400">{summary?.fecha ?? 'Hoy'}</p>
      </div>

      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-4">
        {summary ? (
          <>
            {/* Tarjetas de resumen */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white rounded-2xl p-4 shadow-sm text-center">
                <p className="text-3xl font-bold text-brand-700">{summary.total_tickets}</p>
                <p className="text-xs text-gray-500 mt-1">Tickets</p>
              </div>
              <div className="bg-white rounded-2xl p-4 shadow-sm text-center">
                <p className="text-3xl font-bold text-brand-700">{summary.total_ventas}</p>
                <p className="text-xs text-gray-500 mt-1">Piezas</p>
              </div>
            </div>

            <div className="bg-brand-700 rounded-2xl p-5 text-center shadow">
              <p className="text-white/70 text-sm mb-1">Total generado hoy</p>
              <p className="text-white text-4xl font-bold">
                ${Number(summary.monto_total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
              </p>
            </div>

            {summary.total_tickets === 0 && (
              <div className="text-center py-8">
                <p className="text-4xl mb-3">📊</p>
                <p className="text-gray-500">Sin ventas registradas hoy</p>
                <p className="text-sm text-gray-400 mt-1">Las ventas aparecen cuando se confirman en caja</p>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-12">
            <p className="text-gray-400">No se pudo cargar el resumen</p>
          </div>
        )}
      </div>
    </div>
  )
}
