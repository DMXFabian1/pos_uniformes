import { useState, useEffect } from 'react'
import { salesApi } from '../api/sales'
import Spinner from '../components/Spinner'

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

  useEffect(() => {
    salesApi.list()
      .then(setTickets)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function openDetail(id) {
    setLD(true)
    const t = await salesApi.get(id).catch(() => null)
    if (t) setDetail(t)
    setLD(false)
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <h2 className="font-bold text-gray-900 text-lg">Mis tickets</h2>
        <p className="text-xs text-gray-400">Ventas confirmadas atribuidas a ti</p>
      </div>

      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2">
        {loading && <Spinner className="py-12" />}

        {!loading && tickets.length === 0 && (
          <div className="text-center py-12">
            <p className="text-4xl mb-3">🎫</p>
            <p className="text-gray-500">Sin tickets registrados</p>
          </div>
        )}

        {!loading && tickets.map(t => (
          <button
            key={t.id}
            onClick={() => openDetail(t.id)}
            className="w-full bg-white rounded-2xl p-4 shadow-sm text-left active:shadow-md transition-all"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900 text-sm">{t.folio}</p>
                <p className="text-xs text-gray-400 mt-0.5">{fmtDate(t.confirmada_at ?? t.created_at)}</p>
              </div>
              <p className="font-bold text-brand-700">${fmt(t.total)}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Modal detalle */}
      {(detail || loadingDetail) && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/50" onClick={() => setDetail(null)}>
          <div
            className="w-full bg-white rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            {loadingDetail && <Spinner className="py-8" />}
            {detail && (
              <>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="font-bold text-gray-900">{detail.folio}</p>
                    {detail.cliente_nombre && <p className="text-sm text-gray-500">Cliente: {detail.cliente_nombre}</p>}
                    <p className="text-xs text-gray-400">{fmtDate(detail.confirmada_at)}</p>
                  </div>
                  <button onClick={() => setDetail(null)} className="text-gray-400 text-2xl">×</button>
                </div>

                <div className="space-y-2 mb-4">
                  {detail.lineas.map(l => (
                    <div key={l.id} className="flex items-center justify-between bg-gray-50 rounded-xl px-3 py-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{l.descripcion_snapshot ?? l.sku_snapshot}</p>
                        <p className="text-xs text-gray-400">{l.cantidad} × ${fmt(l.precio_unitario)}</p>
                      </div>
                      <p className="font-semibold text-gray-900 ml-2">${fmt(l.subtotal_linea)}</p>
                    </div>
                  ))}
                </div>

                <div className="border-t border-gray-100 pt-3 space-y-1">
                  {Number(detail.descuento_monto) > 0 && (
                    <div className="flex justify-between text-sm text-gray-500">
                      <span>Descuento</span>
                      <span>−${fmt(detail.descuento_monto)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-lg">
                    <span>Total</span>
                    <span className="text-brand-700">${fmt(detail.total)}</span>
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
