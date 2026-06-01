import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { catalogApi } from '../api/catalog'
import { favoritesApi } from '../api/favorites'
import { useCart } from '../context/CartContext'
import { useToast } from '../components/Toast'
import Spinner from '../components/Spinner'
import { ListSkeleton } from '../components/Skeleton'

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}

const GENERO_LABEL = { HOMBRE: 'Nino', MUJER: 'Nina', UNISEX: 'Todos', NINA: 'Nina', NINO: 'Nino', COMPARTIDO: 'Todos', TODOS: 'Todos' }
const PRENDA_LABEL = { DEPORTIVO: 'Deportivo', OFICIAL: 'Oficial' }

function useFavorites() {
  const [keys, setKeys] = useState(new Set())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    favoritesApi.list()
      .then(data => setKeys(new Set(data.product_keys ?? [])))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function toggle(productKey) {
    setKeys(prev => {
      const next = new Set(prev)
      next.has(productKey) ? next.delete(productKey) : next.add(productKey)
      return next
    })
    try {
      const res = await favoritesApi.toggle(productKey)
      setKeys(prev => {
        const next = new Set(prev)
        res.active ? next.add(productKey) : next.delete(productKey)
        return next
      })
    } catch {
      setKeys(prev => {
        const next = new Set(prev)
        next.has(productKey) ? next.delete(productKey) : next.add(productKey)
        return next
      })
    }
  }

  return { keys, loading, toggle, isFav: (key) => keys.has(key) }
}

function FamilyCard({ family, onAdd, addedSku, isFav, onToggleFav }) {
  const byColor = useMemo(() => {
    const map = {}
    for (const v of family.variantes) {
      if (!map[v.color]) map[v.color] = []
      map[v.color].push(v)
    }
    return map
  }, [family.variantes])

  const colorKeys = Object.keys(byColor)

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0 pr-2">
          <p className="font-bold text-ink-900 leading-tight">{family.nombre_base}</p>
          {family.tipo_pieza && (
            <span className="inline-block mt-1.5 text-[11px] bg-surface-100 text-ink-500 px-2.5 py-0.5 rounded-lg border border-surface-200 font-medium">
              {family.tipo_pieza}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="text-right">
            <p className="font-extrabold text-brand-600 text-lg">${fmt(family.precio_desde)}</p>
            {family.variantes.length > 1 && (
              <p className="text-[10px] text-ink-400">desde</p>
            )}
          </div>
          <button
            onClick={onToggleFav}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-90 touch-target
              ${isFav ? 'bg-brand-100 text-brand-600' : 'bg-surface-100 text-ink-300'}`}
            title={isFav ? 'Quitar de favoritos' : 'Agregar a favoritos'}
          >
            <svg className="w-5 h-5" fill={isFav ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
            </svg>
          </button>
        </div>
      </div>

      <div className="space-y-2.5">
        {colorKeys.map(color => (
          <div key={color} className="flex items-center gap-2.5">
            {color.toLowerCase() !== 'sin color' && (
            <span className="text-[11px] text-ink-400 font-medium shrink-0 w-20 truncate" title={color}>
              {color}
            </span>
          )}
            <div className="flex gap-1.5 flex-wrap">
              {byColor[color].map(v => {
                const isAdded = addedSku === v.sku
                return (
                  <button
                    key={v.sku}
                    onClick={() => onAdd(v, family.nombre_base)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all duration-150 touch-target
                      ${isAdded
                        ? 'bg-success-500 text-white scale-90'
                        : 'bg-surface-100 text-ink-700 border border-surface-200 active:bg-brand-600 active:text-white active:border-brand-600 active:scale-95'
                      }`}
                  >
                    {isAdded ? '✓' : v.talla}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
        {colorKeys.length === 0 && (
          <p className="text-xs text-ink-400 text-center py-2">Sin variantes disponibles</p>
        )}
      </div>
    </div>
  )
}

function FilterChips({ options, selected, onSelect, labelFn }) {
  if (!options || options.length === 0) return null
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      {options.map(opt => {
        const key   = typeof opt === 'object' ? opt.id   : opt
        const label = typeof opt === 'object' ? opt.nombre : (labelFn?.(opt) ?? opt)
        const active = selected === key
        return (
          <button
            key={key}
            onClick={() => onSelect(active ? null : key)}
            className={`chip touch-target ${active ? 'chip-active' : 'chip-inactive'}`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

function StepList({ items, onSelect, filterKey = 'nombre', badgeFn }) {
  const [q, setQ] = useState('')
  const filtered = items.filter(it =>
    it[filterKey].toLowerCase().includes(q.toLowerCase())
  )
  return (
    <div className="flex flex-col gap-0 h-full">
      {items.length > 6 && (
        <div className="px-4 pb-3">
          <input
            type="search"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Buscar..."
            className="input-field"
          />
        </div>
      )}
      <div className="flex-1 overflow-y-auto overscroll-contain space-y-2 px-4">
        {filtered.map(it => (
          <button
            key={it.id}
            onClick={() => onSelect(it)}
            className="w-full flex items-center justify-between card px-4 py-4
              active:shadow-card-hover active:scale-[0.99] transition-all text-left touch-target"
          >
            <span className="font-semibold text-ink-900 text-sm">{it[filterKey]}</span>
            {badgeFn && (
              <span className="text-xs text-ink-400 bg-surface-100 px-2.5 py-1 rounded-lg shrink-0 ml-2 border border-surface-200 font-medium">
                {badgeFn(it)}
              </span>
            )}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-center text-ink-400 text-sm py-8">Sin resultados</p>
        )}
      </div>
    </div>
  )
}

export default function CatalogScreen() {
  const [mode,        setMode]        = useState(null)
  const [nivelId,     setNivelId]     = useState(null)
  const [escuelaId,   setEscuelaId]   = useState(null)
  const [tipoPrenda,  setTipoPrenda]  = useState(null)
  const [genero,      setGenero]      = useState(null)
  const [tipoPiezaId, setTipoPiezaId] = useState(null)

  const [options,     setOptions]     = useState(null)
  const [loadingOpts, setLoadingOpts] = useState(true)
  const [products,    setProducts]    = useState(null)
  const [loadingProd, setLoadingProd] = useState(false)

  const [tab,        setTab]        = useState('guided')
  const [q,          setQ]          = useState('')
  const [searchData, setSearchData] = useState(null)
  const [searchPage, setSearchPage] = useState(1)
  const [searchLoad, setSearchLoad] = useState(false)
  const [detail,     setDetail]     = useState(null)
  const searchDebounce = useRef(null)

  const [quickQ,          setQuickQ]          = useState('')
  const [quickResults,    setQuickResults]    = useState(null)
  const [quickLoading,    setQuickLoading]    = useState(false)
  const quickDebounce = useRef(null)

  const { keys: favKeys, isFav, toggle: toggleFav } = useFavorites()

  const { client, lines, addLine } = useCart()
  const { show: toast } = useToast()
  const navigate = useNavigate()
  const [addedSku, setAddedSku] = useState(null)

  useEffect(() => {
    setLoadingOpts(true)
    catalogApi.guidedOptions()
      .then(setOptions)
      .catch(() => {})
      .finally(() => setLoadingOpts(false))
  }, [])

  useEffect(() => {
    if (!mode) { setProducts(null); return }
    if (mode === 'school' && !escuelaId) { setProducts(null); return }

    setLoadingProd(true)
    catalogApi.guidedProducts({ mode, escuela_id: escuelaId, tipo_prenda: tipoPrenda, genero, tipo_pieza_id: tipoPiezaId })
      .then(setProducts)
      .catch(() => {})
      .finally(() => setLoadingProd(false))
  }, [mode, escuelaId, tipoPrenda, genero, tipoPiezaId])

  const runSearch = useCallback((query, page) => {
    setSearchLoad(true)
    catalogApi.list(query, page)
      .then(setSearchData)
      .catch(() => {})
      .finally(() => setSearchLoad(false))
  }, [])

  useEffect(() => {
    if (tab !== 'search') return
    clearTimeout(searchDebounce.current)
    searchDebounce.current = setTimeout(() => { runSearch(q, 1); setSearchPage(1) }, 300)
    return () => clearTimeout(searchDebounce.current)
  }, [q, tab, runSearch])

  useEffect(() => {
    if (tab === 'search' && !searchData) runSearch('', 1)
  }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!quickQ.trim()) { setQuickResults(null); return }
    clearTimeout(quickDebounce.current)
    quickDebounce.current = setTimeout(() => {
      setQuickLoading(true)
      catalogApi.quickSearch(quickQ.trim())
        .then(data => setQuickResults(data?.families ?? []))
        .catch(() => setQuickResults(null))
        .finally(() => setQuickLoading(false))
    }, 250)
    return () => clearTimeout(quickDebounce.current)
  }, [quickQ])

  async function openDetail(id) {
    const prod = await catalogApi.get(id).catch(() => null)
    if (prod) setDetail(prod)
  }

  function handleAdd(variante, nombre) {
    addLine(
      { sku: variante.sku, talla: variante.talla, color: variante.color, precio_venta: Number(variante.precio_venta) },
      { nombre }
    )
    setAddedSku(variante.sku)
    if (navigator.vibrate) navigator.vibrate(40)
    toast(`${nombre} T${variante.talla} agregado`)
    setTimeout(() => setAddedSku(null), 900)
  }

  const nivel   = useMemo(() => options?.niveles.find(n => n.id === nivelId), [options, nivelId])
  const escuela = useMemo(() => nivel?.escuelas.find(e => e.id === escuelaId), [nivel, escuelaId])

  const crumbs = useMemo(() => {
    const items = []
    if (!mode) return items
    items.push({
      label: mode === 'school' ? 'Uniformes' : 'Basicos',
      onClick: () => { setMode(null); setNivelId(null); setEscuelaId(null); setTipoPrenda(null); setGenero(null); setTipoPiezaId(null) },
    })
    if (mode === 'school' && nivelId && nivel) {
      items.push({
        label: nivel.nombre,
        onClick: () => { setNivelId(null); setEscuelaId(null); setTipoPrenda(null); setGenero(null); setTipoPiezaId(null) },
      })
    }
    if (mode === 'school' && escuelaId && escuela) {
      items.push({
        label: escuela.nombre,
        onClick: () => { setEscuelaId(null); setTipoPrenda(null); setGenero(null); setTipoPiezaId(null) },
      })
    }
    return items
  }, [mode, nivelId, nivel, escuelaId, escuela])

  const step = useMemo(() => {
    if (!mode)                           return 'mode'
    if (mode === 'school' && !nivelId)   return 'nivel'
    if (mode === 'school' && !escuelaId) return 'escuela'
    return 'products'
  }, [mode, nivelId, escuelaId])

  const cartTotal = lines.reduce((acc, l) => acc + Number(l.subtotal), 0)

  return (
    <div className="flex flex-col h-full bg-surface-50">

      {/* Header */}
      <div className="bg-surface-0 px-4 pt-4 pb-3 border-b border-surface-200 space-y-2.5 shrink-0">
        {client && (
          <div className="flex items-center gap-2 bg-brand-50 border border-brand-200 rounded-xl px-3 py-2">
            <span className="text-brand-600 text-sm">👤</span>
            <span className="text-brand-800 text-sm font-medium flex-1 truncate">{client.nombre}</span>
          </div>
        )}
        <div className="flex gap-1 bg-surface-100 rounded-xl p-1 border border-surface-200">
          <button
            onClick={() => setTab('guided')}
            className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all
              ${tab === 'guided' ? 'bg-surface-0 text-ink-900 shadow-card' : 'text-ink-400'}`}
          >
            Guiado
          </button>
          <button
            onClick={() => { setTab('favorites'); setMode(null) }}
            className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all
              ${tab === 'favorites' ? 'bg-surface-0 text-ink-900 shadow-card' : 'text-ink-400'}`}
          >
            Favoritos
            {favKeys.size > 0 && (
              <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full font-bold
                ${tab === 'favorites' ? 'bg-brand-100 text-brand-700' : 'bg-surface-200 text-ink-500'}`}>
                {favKeys.size}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* TAB: FAVORITOS */}
      {tab === 'favorites' && (
        <FavoritesTab
          favKeys={favKeys}
          isFav={isFav}
          toggleFav={toggleFav}
          onAdd={handleAdd}
          addedSku={addedSku}
        />
      )}

      {/* TAB: BUSQUEDA */}
      {tab === 'search' && (
        <>
          <div className="bg-surface-0 px-4 pb-3 border-b border-surface-200 shrink-0">
            <div className="relative">
              <input
                type="search"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Buscar producto, SKU o categoria..."
                className="input-field pl-10"
                autoFocus
              />
              <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-300" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2.5">
            {searchLoad && <ListSkeleton count={4} />}
            {!searchLoad && searchData?.items.map(p => (
              <button
                key={p.id}
                onClick={() => openDetail(p.id)}
                className="w-full card p-4 flex items-center gap-3 text-left active:scale-[0.99] transition-all touch-target"
              >
                <div className="w-11 h-11 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-500 shrink-0">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007zM8.625 10.5a.375.375 0 11-.75 0 .375.375 0 01.75 0zm7.5 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-ink-900 truncate text-sm">{p.nombre}</p>
                  <p className="text-xs text-ink-400 mt-0.5">{p.categoria} · {p.total_variantes} talla{p.total_variantes !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-brand-600">${fmt(p.precio_desde)}</p>
                  <p className="text-[10px] text-ink-400">desde</p>
                </div>
              </button>
            ))}
            {!searchLoad && searchData?.items.length === 0 && (
              <p className="text-center text-ink-400 py-12 text-sm">Sin resultados para "{q}"</p>
            )}
            {!searchLoad && searchData && searchData.total > searchData.page_size && (
              <div className="flex gap-2.5 pt-2 pb-4">
                <button disabled={searchPage === 1}
                  onClick={() => { const p = searchPage - 1; setSearchPage(p); runSearch(q, p) }}
                  className="flex-1 btn-secondary py-2.5 text-sm disabled:opacity-40">
                  Anterior
                </button>
                <button disabled={searchData.page * searchData.page_size >= searchData.total}
                  onClick={() => { const p = searchPage + 1; setSearchPage(p); runSearch(q, p) }}
                  className="flex-1 btn-secondary py-2.5 text-sm disabled:opacity-40">
                  Siguiente
                </button>
              </div>
            )}
          </div>

          {detail && (
            <div className="fixed inset-0 z-50 flex items-end animate-fade-in" onClick={() => setDetail(null)}>
              <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-[2px]" />
              <div className="relative w-full bg-surface-0 rounded-t-3xl p-5 max-h-[80vh] overflow-y-auto shadow-float animate-slide-up" onClick={e => e.stopPropagation()}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-ink-900 text-lg leading-tight">{detail.nombre}</h3>
                    <p className="text-sm text-ink-400 mt-0.5">{detail.categoria} · {detail.marca}</p>
                  </div>
                  <button onClick={() => setDetail(null)} className="text-ink-300 active:text-ink-700 w-10 h-10 flex items-center justify-center rounded-xl active:bg-surface-100 touch-target">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="space-y-2">
                  {detail.variantes.map(v => (
                    <div key={v.id} className="flex items-center gap-3 bg-surface-100 rounded-xl p-3.5 border border-surface-200">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-ink-900">{v.talla} · {v.color}</p>
                        <p className="text-xs text-ink-400 mt-0.5">{v.sku}</p>
                      </div>
                      <p className="font-bold text-brand-600 mr-2">${fmt(v.precio_venta)}</p>
                      <button
                        onClick={() => handleAdd(v, detail.nombre)}
                        className={`shrink-0 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all touch-target
                          ${addedSku === v.sku ? 'bg-success-500 text-white scale-95' : 'btn-primary'}`}
                      >
                        {addedSku === v.sku ? '✓' : 'Agregar'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* TAB: GUIADO */}
      {tab === 'guided' && (
        <>
          <div className="bg-surface-0 px-4 py-2.5 border-b border-surface-200 shrink-0">
            <div className="relative">
              <input
                type="search"
                value={quickQ}
                onChange={e => setQuickQ(e.target.value)}
                placeholder="Busqueda rapida..."
                className="input-field pl-10"
              />
              <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-300" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              {quickQ && (
                <button
                  onClick={() => { setQuickQ(''); setQuickResults(null) }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-300 active:text-ink-700 w-6 h-6 flex items-center justify-center"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {quickQ.trim() && (
            <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-3">
              {quickLoading && <ListSkeleton count={3} />}
              {!quickLoading && quickResults && quickResults.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <div className="w-14 h-14 rounded-2xl bg-surface-100 border border-surface-200 flex items-center justify-center">
                    <svg className="w-7 h-7 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                    </svg>
                  </div>
                  <p className="text-ink-400 text-sm text-center">Sin resultados para "{quickQ}"</p>
                </div>
              )}
              {!quickLoading && quickResults && quickResults.map(family => (
                <FamilyCard
                  key={family.key}
                  family={family}
                  onAdd={handleAdd}
                  addedSku={addedSku}
                  isFav={isFav(family.key)}
                  onToggleFav={() => toggleFav(family.key)}
                />
              ))}
            </div>
          )}

          {!quickQ.trim() && crumbs.length > 0 && (
            <div className="bg-surface-0 px-4 py-2.5 border-b border-surface-200 shrink-0">
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
                <button
                  onClick={crumbs[0].onClick}
                  className="shrink-0 btn-ghost text-sm px-2 py-1"
                >
                  <svg className="w-4 h-4 inline mr-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                  </svg>
                  Atras
                </button>
                <span className="text-surface-300 mx-0.5">|</span>
                {crumbs.map((c, i) => (
                  <span key={i} className="flex items-center gap-1 shrink-0">
                    {i > 0 && <span className="text-surface-300 text-xs">›</span>}
                    <button
                      onClick={c.onClick}
                      className="text-sm text-ink-500 font-medium max-w-[120px] truncate active:text-brand-600"
                    >
                      {c.label}
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {!quickQ.trim() && loadingOpts && step === 'mode' && <Spinner className="flex-1" />}

          {!quickQ.trim() && step === 'mode' && !loadingOpts && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 gap-4">
              <p className="text-ink-400 text-sm mb-2">Que tipo de productos?</p>
              <div className="w-full grid grid-cols-2 gap-4">
                <button
                  onClick={() => setMode('school')}
                  className="flex flex-col items-center gap-3 card p-6
                    active:border-brand-400 active:bg-brand-50 transition-all active:scale-[0.97]"
                >
                  <div className="w-14 h-14 rounded-2xl bg-brand-50 border border-brand-100 flex items-center justify-center">
                    <svg className="w-7 h-7 text-brand-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5" />
                    </svg>
                  </div>
                  <span className="font-bold text-ink-900 text-center text-sm leading-tight">
                    Uniformes Escolares
                  </span>
                  {options && (
                    <span className="text-xs text-ink-400">{options.niveles.length} niveles</span>
                  )}
                </button>
                <button
                  onClick={() => setMode('basics')}
                  className="flex flex-col items-center gap-3 card p-6
                    active:border-brand-400 active:bg-brand-50 transition-all active:scale-[0.97]"
                >
                  <div className="w-14 h-14 rounded-2xl bg-surface-100 border border-surface-200 flex items-center justify-center">
                    <svg className="w-7 h-7 text-ink-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                    </svg>
                  </div>
                  <span className="font-bold text-ink-900 text-center text-sm leading-tight">
                    Basicos
                  </span>
                  {options && (
                    <span className="text-xs text-ink-400">{options.tipo_pieza_basics.length} tipos</span>
                  )}
                </button>
              </div>
            </div>
          )}

          {!quickQ.trim() && step === 'nivel' && options && (
            <div className="flex-1 min-h-0 py-3">
              <p className="text-xs text-ink-400 uppercase tracking-wide font-semibold px-4 mb-3">
                Nivel educativo
              </p>
              <StepList
                items={options.niveles}
                onSelect={n => setNivelId(n.id)}
                badgeFn={n => `${n.escuelas.length} escuela${n.escuelas.length !== 1 ? 's' : ''}`}
              />
            </div>
          )}

          {!quickQ.trim() && step === 'escuela' && nivel && (
            <div className="flex-1 min-h-0 py-3">
              <p className="text-xs text-ink-400 uppercase tracking-wide font-semibold px-4 mb-3">
                Escuela — {nivel.nombre}
              </p>
              <StepList
                items={nivel.escuelas}
                onSelect={e => setEscuelaId(e.id)}
              />
            </div>
          )}

          {!quickQ.trim() && step === 'products' && (
            <div className="flex-1 min-h-0 flex flex-col">
              {(products?.tipo_prenda_options?.length > 0
                || products?.genero_options?.length > 1
                || products?.tipo_pieza_options?.length > 0
                || options?.tipo_pieza_basics?.length > 0
              ) && (
                <div className="bg-surface-0 border-b border-surface-200 px-4 py-3 shrink-0 space-y-2.5">
                  {mode === 'school' && products?.tipo_prenda_options?.length > 0 && (
                    <FilterChips
                      options={products.tipo_prenda_options}
                      selected={tipoPrenda}
                      onSelect={val => { setTipoPrenda(val); setGenero(null) }}
                      labelFn={v => PRENDA_LABEL[v] ?? v}
                    />
                  )}
                  {mode === 'school' && tipoPrenda && products?.genero_options?.length > 1 && (
                    <FilterChips
                      options={products.genero_options}
                      selected={genero}
                      onSelect={setGenero}
                      labelFn={v => GENERO_LABEL[v] ?? v}
                    />
                  )}
                  {(() => {
                    const piezaOpts = mode === 'school'
                      ? products?.tipo_pieza_options
                      : options?.tipo_pieza_basics
                    if (!piezaOpts?.length) return null
                    return (
                      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
                        <button
                          onClick={() => setTipoPiezaId(null)}
                          className={`chip touch-target ${!tipoPiezaId ? 'chip-active' : 'chip-inactive'}`}
                        >
                          Todas
                        </button>
                        {piezaOpts.map(tp => (
                          <button
                            key={tp.id}
                            onClick={() => setTipoPiezaId(tipoPiezaId === tp.id ? null : tp.id)}
                            className={`chip touch-target ${tipoPiezaId === tp.id ? 'chip-active' : 'chip-inactive'}`}
                          >
                            {tp.nombre}
                          </button>
                        ))}
                      </div>
                    )
                  })()}
                </div>
              )}

              <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-3">
                {loadingProd && <ListSkeleton count={3} />}

                {!loadingProd && products?.families?.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <div className="w-14 h-14 rounded-2xl bg-surface-100 border border-surface-200 flex items-center justify-center">
                      <svg className="w-7 h-7 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                      </svg>
                    </div>
                    <p className="text-ink-400 text-sm text-center">
                      Sin productos para esta seleccion.
                      {mode === 'school' && !tipoPrenda && ' Selecciona un tipo de uniforme.'}
                    </p>
                  </div>
                )}

                {!loadingProd && products?.families?.map(family => (
                  <FamilyCard
                    key={family.key}
                    family={family}
                    onAdd={handleAdd}
                    addedSku={addedSku}
                    isFav={isFav(family.key)}
                    onToggleFav={() => toggleFav(family.key)}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}

    </div>
  )
}

function FavoritesTab({ favKeys, isFav, toggleFav, onAdd, addedSku }) {
  const [families,  setFamilies]  = useState(null)
  const [loading,   setLoading]   = useState(false)

  useEffect(() => {
    if (favKeys.size === 0) { setFamilies([]); return }
    setLoading(true)
    Promise.all([
      catalogApi.guidedProducts({ mode: 'basics' }).catch(() => ({ families: [] })),
      catalogApi.guidedProducts({ mode: 'school' }).catch(() => ({ families: [] })),
    ]).then(([basics, school]) => {
      const all = [...(basics.families ?? []), ...(school.families ?? [])]
      const favs = all.filter(f => favKeys.has(f.key))
      const seen = new Set()
      const unique = favs.filter(f => { if (seen.has(f.key)) return false; seen.add(f.key); return true })
      const PIEZA_ORDER = ['Pantalon', 'Falda', 'Sueter', 'Camisa', 'Playera', 'Calceta', 'Malla']
      const piezaRank = (f) => {
        const i = PIEZA_ORDER.indexOf(f.tipo_pieza ?? '')
        return i === -1 ? PIEZA_ORDER.length : i
      }
      unique.sort((a, b) => {
        const dr = piezaRank(a) - piezaRank(b)
        if (dr !== 0) return dr
        return a.nombre_base.localeCompare(b.nombre_base, 'es', { sensitivity: 'base' })
      })
      setFamilies(unique)
    }).finally(() => setLoading(false))
  }, [favKeys])

  if (loading) return <div className="flex-1 p-4"><ListSkeleton count={3} /></div>

  if (!families || families.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-8 gap-4 text-center">
        <div className="w-16 h-16 rounded-3xl bg-surface-100 border border-surface-200 flex items-center justify-center">
          <svg className="w-8 h-8 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
          </svg>
        </div>
        <p className="font-semibold text-ink-700">Sin favoritos</p>
        <p className="text-sm text-ink-400">
          Toca el corazon en las piezas del catalogo guiado para marcarlas aqui.
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-3">
      {families.map(family => (
        <FamilyCard
          key={family.key}
          family={family}
          onAdd={onAdd}
          addedSku={addedSku}
          isFav={isFav(family.key)}
          onToggleFav={() => toggleFav(family.key)}
        />
      ))}
    </div>
  )
}
