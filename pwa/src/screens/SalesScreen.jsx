import { useState, useEffect, useCallback } from 'react'
import { salesApi } from '../api/sales'
import { ListSkeleton } from '../components/Skeleton'
import PullToRefresh from '../components/PullToRefresh'

export default function SalesScreen() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadSales = useCallback(() => {
    return salesApi.today()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadSales() }, [loadSales])

  if (loading) return (
    <div className="flex flex-col h-full bg-surface-50 p-4">
      <ListSkeleton count={2} />
    </div>
  )

  return (
    <div className="flex flex-col h-full bg-surface-50">
      <div className="bg-surface-0 px-5 pt-5 pb-4 border-b border-surface-200">
        <h2 className="font-bold text-ink-900 text-lg">Mis ventas de hoy</h2>
        <p className="text-xs text-ink-400 mt-0.5">{summary?.fecha ?? 'Hoy'}</p>
      </div>

      <PullToRefresh onRefresh={loadSales} className="flex-1 px-4 py-5 space-y-4">
        {summary ? (
          <>
            <div className="bg-brand-600 rounded-3xl p-6 text-center shadow-card">
              <p className="text-white/70 text-sm mb-2">Total generado hoy</p>
              <p className="text-white text-4xl font-bold tracking-tight">
                ${Number(summary.monto_total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="card p-5 text-center">
                <p className="text-3xl font-bold text-ink-900">{summary.total_tickets}</p>
                <p className="text-xs text-ink-400 mt-1 font-medium">Tickets</p>
              </div>
              <div className="card p-5 text-center">
                <p className="text-3xl font-bold text-ink-900">{summary.total_ventas}</p>
                <p className="text-xs text-ink-400 mt-1 font-medium">Piezas</p>
              </div>
            </div>

            {summary.total_tickets === 0 && (
              <div className="text-center py-8">
                <div className="w-14 h-14 rounded-2xl bg-surface-100 border border-surface-200 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-7 h-7 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                  </svg>
                </div>
                <p className="text-ink-500 font-medium">Sin ventas registradas hoy</p>
                <p className="text-sm text-ink-400 mt-1">Aparecen cuando se confirman en caja</p>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-12">
            <p className="text-ink-400">No se pudo cargar el resumen</p>
          </div>
        )}
      </PullToRefresh>
    </div>
  )
}
