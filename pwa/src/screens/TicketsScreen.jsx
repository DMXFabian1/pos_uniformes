import { useState, useEffect, useCallback } from 'react'
import { salesApi } from '../api/sales'
import { ListSkeleton } from '../components/Skeleton'
import PullToRefresh from '../components/PullToRefresh'

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}
function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export default function TicketsScreen() {
  const [tickets, setTickets]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [detail, setDetail]     = useState(null)
  const [loadingDetail, setLD]  = useState(false)

  const loadTickets = useCallback(() => {
    return salesApi.list()
      .then(setTickets)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadTickets() }, [loadTickets])

  async function openDetail(id) {
    setLD(true)
    const t = await salesApi.get(id).catch(() => null)
    if (t) setDetail(t)
    setLD(false)
  }

  return (
    <div className="flex flex-col h-full bg-surface-50">
      <div className="bg-surface-0 px-5 pt-5 pb-4 border-b border-surface-200">
        <h2 className="font-bold text-ink-900 text-lg">Mis tickets</h2>
        <p className="text-xs text-ink-400 mt-0.5">Ventas confirmadas atribuidas a ti</p>
      </div>

      <PullToRefresh onRefresh={loadTickets} className="flex-1 px-4 py-4 space-y-2.5">
        {loading && <ListSkeleton count={4} />}

        {!loading && tickets.length === 0 && (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-3xl bg-surface-100 border border-surface-200 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z" />
              </svg>
            </div>
            <p className="text-ink-700 font-semibold">Sin tickets registrados</p>
          </div>
        )}

        {!loading && tickets.map(t => (
          <button
            key={t.id}
            onClick={() => openDetail(t.id)}
            className="w-full card p-4 text-left active:shadow-card-hover active:scale-[0.99] transition-all touch-target"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold text-ink-900 text-sm">{t.folio}</p>
                <p className="text-xs text-ink-400 mt-0.5">{fmtDate(t.confirmada_at ?? t.created_at)}</p>
              </div>
              <p className="font-bold text-brand-600">${fmt(t.total)}</p>
            </div>
          </button>
        ))}
      </PullToRefresh>

      {(detail || loadingDetail) && (
        <div className="fixed inset-0 z-50 flex items-end animate-fade-in" onClick={() => setDetail(null)}>
          <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-[2px]" />
          <div
            className="relative w-full bg-surface-0 rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto shadow-float animate-slide-up"
            onClick={e => e.stopPropagation()}
          >
            {loadingDetail && <div className="py-8"><ListSkeleton count={2} /></div>}
            {detail && (
              <>
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <p className="font-bold text-ink-900 text-lg">{detail.folio}</p>
                    {detail.cliente_nombre && <p className="text-sm text-ink-500 mt-0.5">Cliente: {detail.cliente_nombre}</p>}
                    <p className="text-xs text-ink-400 mt-0.5">{fmtDate(detail.confirmada_at)}</p>
                  </div>
                  <button onClick={() => setDetail(null)} className="text-ink-300 active:text-ink-700 w-10 h-10 flex items-center justify-center rounded-xl active:bg-surface-100 transition-colors touch-target">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-2 mb-5">
                  {detail.lineas.map(l => (
                    <div key={l.id} className="flex items-center justify-between bg-surface-100 rounded-xl px-4 py-3 border border-surface-200">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-ink-900 truncate">{l.descripcion_snapshot ?? l.sku_snapshot}</p>
                        <p className="text-xs text-ink-400 mt-0.5">{l.cantidad} x ${fmt(l.precio_unitario)}</p>
                      </div>
                      <p className="font-semibold text-ink-900 ml-3">${fmt(l.subtotal_linea)}</p>
                    </div>
                  ))}
                </div>

                <div className="border-t border-surface-200 pt-4 space-y-2">
                  {Number(detail.descuento_monto) > 0 && (
                    <div className="flex justify-between text-sm text-ink-500">
                      <span>Descuento</span>
                      <span className="text-success-500 font-medium">-${fmt(detail.descuento_monto)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-lg">
                    <span className="text-ink-700">Total</span>
                    <span className="text-brand-600">${fmt(detail.total)}</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
