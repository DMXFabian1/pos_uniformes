import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'
import Spinner from '../components/Spinner'

export default function CatalogScreen() {
  const [q, setQ]             = useState('')
  const [page, setPage]       = useState(1)
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail]   = useState(null)
  const [added, setAdded]     = useState(null)
  const { client, lines, addLine } = useCart()
  const navigate              = useNavigate()
  const debounce              = useRef(null)

  const load = useCallback((query, p) => {
    setLoading(true)
    catalogApi.list(query, p)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    clearTimeout(debounce.current)
    debounce.current = setTimeout(() => { load(q, 1); setPage(1) }, 300)
    return () => clearTimeout(debounce.current)
  }, [q, load])

  async function openDetail(id) {
    const prod = await catalogApi.get(id).catch(() => null)
    if (prod) setDetail(prod)
  }

  function handleAdd(variante) {
    addLine(variante, detail)
    setAdded(variante.sku)
    setTimeout(() => setAdded(null), 1200)
  }

  const total = lines.reduce((acc, l) => acc + Number(l.subtotal), 0)

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100 space-y-3">
        {client && (
          <div className="flex items-center gap-2 bg-brand-50 rounded-xl px-3 py-2">
            <span className="text-brand-700 text-sm">👤</span>
            <span className="text-brand-800 text-sm font-medium">{client.nombre}</span>
            <span className="ml-auto text-brand-500 text-xs">{client.tipo_cliente}</span>
          </div>
        )}
        <div className="relative">
          <input
            type="search"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Buscar producto, SKU o categoría…"
            className="w-full bg-gray-100 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-brand-400 pl-9"
          />
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
        </div>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2">
        {loading && <Spinner className="py-12" />}

        {!loading && data?.items.map(p => (
          <button
            key={p.id}
            onClick={() => openDetail(p.id)}
            className="w-full bg-white rounded-2xl p-4 flex items-center gap-3 text-left shadow-sm active:shadow-md active:scale-[0.99] transition-all"
          >
            <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-brand-600 text-lg shrink-0">
              👕
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 truncate">{p.nombre}</p>
              <p className="text-xs text-gray-500">{p.categoria} · {p.total_variantes} talla{p.total_variantes !== 1 ? 's' : ''}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="font-bold text-brand-700">
                ${Number(p.precio_desde).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-[10px] text-gray-400">desde</p>
            </div>
          </button>
        ))}

        {!loading && data?.items.length === 0 && (
          <p className="text-center text-gray-400 py-12">Sin resultados para "{q}"</p>
        )}

        {/* Paginacion */}
        {!loading && data && data.total > data.page_size && (
          <div className="flex gap-2 pt-2 pb-4">
            <button
              disabled={page === 1}
              onClick={() => { setPage(p => p - 1); load(q, page - 1) }}
              className="flex-1 py-2 bg-white rounded-xl border border-gray-200 text-sm disabled:opacity-40"
            >
              ← Anterior
            </button>
            <button
              disabled={data.page * data.page_size >= data.total}
              onClick={() => { setPage(p => p + 1); load(q, page + 1) }}
              className="flex-1 py-2 bg-white rounded-xl border border-gray-200 text-sm disabled:opacity-40"
            >
              Siguiente →
            </button>
          </div>
        )}
      </div>

      {/* Carrito flotante */}
      {lines.length > 0 && (
        <div className="px-4 pb-2">
          <button
            onClick={() => navigate('/quotes/current')}
            className="w-full bg-brand-700 text-white rounded-2xl px-4 py-4 flex items-center justify-between shadow-lg active:bg-brand-800"
          >
            <span className="font-semibold">Ver presupuesto ({lines.length})</span>
            <span className="font-bold text-lg">
              ${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
            </span>
          </button>
        </div>
      )}

      {/* Modal de detalle */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/50" onClick={() => setDetail(null)}>
          <div
            className="w-full bg-white rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="font-bold text-gray-900 text-lg">{detail.nombre}</h3>
                <p className="text-sm text-gray-500">{detail.categoria} · {detail.marca}</p>
              </div>
              <button onClick={() => setDetail(null)} className="text-gray-400 text-2xl leading-none">×</button>
            </div>

            <div className="space-y-2">
              {detail.variantes.map(v => (
                <div key={v.id} className="flex items-center gap-3 bg-gray-50 rounded-xl p-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{v.talla} · {v.color}</p>
                    <p className="text-xs text-gray-400">{v.sku}</p>
                  </div>
                  <p className="font-bold text-brand-700 mr-2">
                    ${Number(v.precio_venta).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </p>
                  {/* BOTON PRINCIPAL DE ACCION */}
                  <button
                    onClick={() => handleAdd(v)}
                    className={`shrink-0 px-4 py-2 rounded-xl font-semibold text-sm transition-all
                      ${added === v.sku
                        ? 'bg-green-500 text-white scale-95'
                        : 'bg-brand-700 text-white active:bg-brand-800'
                      }`}
                  >
                    {added === v.sku ? '✓ Agregado' : 'Agregar'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
