/**
 * Catálogo guiado — presupuesto guiado mobile
 *
 * Flujo school:  Modo → Nivel → Escuela → [DEPORTIVO|OFICIAL] → [Niña|Niño] → Pieza → Productos
 * Flujo basics:  Modo → Pieza → Productos
 * Tab Buscar:    búsqueda libre de texto (fallback)
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'
import Spinner from '../components/Spinner'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}

const GENERO_LABEL = { NINA: '👧 Niña', NINO: '👦 Niño', COMPARTIDO: '👫 Compartido', TODOS: '👫 Todos' }
const PRENDA_LABEL = { DEPORTIVO: '⚽ Deportivo', OFICIAL: '🎓 Oficial' }

// ── FamilyCard ────────────────────────────────────────────────────────────────

function FamilyCard({ family, onAdd, addedSku }) {
  // Agrupar variantes por color
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
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      {/* Encabezado de familia */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0 pr-3">
          <p className="font-bold text-gray-900 leading-tight">{family.nombre_base}</p>
          {family.tipo_pieza && (
            <span className="inline-block mt-1 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
              {family.tipo_pieza}
            </span>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="font-extrabold text-brand-700 text-lg">${fmt(family.precio_desde)}</p>
          {family.variantes.length > 1 && (
            <p className="text-[10px] text-gray-400">desde</p>
          )}
        </div>
      </div>

      {/* Variantes agrupadas por color */}
      <div className="space-y-2">
        {colorKeys.map(color => (
          <div key={color} className="flex items-center gap-2 flex-wrap">
            {/* Etiqueta de color */}
            <span className="text-xs text-gray-500 font-medium shrink-0 w-20 truncate" title={color}>
              {color}
            </span>
            {/* Chips de talla */}
            <div className="flex gap-1.5 flex-wrap">
              {byColor[color].map(v => {
                const isAdded = addedSku === v.sku
                return (
                  <button
                    key={v.sku}
                    onClick={() => onAdd(v, family.nombre_base)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-150
                      ${isAdded
                        ? 'bg-green-500 text-white scale-90'
                        : 'bg-gray-100 text-gray-700 active:bg-brand-700 active:text-white active:scale-95'
                      }`}
                  >
                    {isAdded ? '✓' : v.talla}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Precio total si hay variante seleccionada */}
      {colorKeys.length === 0 && (
        <p className="text-xs text-gray-400 text-center py-2">Sin variantes disponibles</p>
      )}
    </div>
  )
}

// ── FilterChips ───────────────────────────────────────────────────────────────

function FilterChips({ options, selected, onSelect, labelFn }) {
  if (!options || options.length === 0) return null
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      {options.map(opt => {
        const key   = typeof opt === 'object' ? opt.id   : opt
        const label = typeof opt === 'object' ? opt.nombre : (labelFn?.(opt) ?? opt)
        const isSelected = selected === key
        return (
          <button
            key={key}
            onClick={() => onSelect(isSelected ? null : key)}
            className={`shrink-0 px-4 py-2 rounded-full text-sm font-semibold transition-all
              ${isSelected
                ? 'bg-brand-700 text-white shadow-md shadow-brand-700/30'
                : 'bg-gray-100 text-gray-700 active:bg-gray-200'
              }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

// ── StepList — lista de opciones tipo "nivel" o "escuela" ─────────────────────

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
            placeholder="Buscar…"
            className="w-full bg-gray-100 rounded-xl px-4 py-2.5 text-sm outline-none"
          />
        </div>
      )}
      <div className="flex-1 overflow-y-auto overscroll-contain space-y-1.5 px-4">
        {filtered.map(it => (
          <button
            key={it.id}
            onClick={() => onSelect(it)}
            className="w-full flex items-center justify-between bg-white rounded-2xl px-4 py-3.5
              shadow-sm border border-gray-100 active:bg-brand-50 active:border-brand-200 text-left"
          >
            <span className="font-medium text-gray-900 text-sm">{it[filterKey]}</span>
            {badgeFn && (
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full shrink-0">
                {badgeFn(it)}
              </span>
            )}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-center text-gray-400 text-sm py-8">Sin resultados</p>
        )}
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function CatalogScreen() {
  // ── Filtros ──
  const [mode,        setMode]        = useState(null)    // 'school' | 'basics'
  const [nivelId,     setNivelId]     = useState(null)
  const [escuelaId,   setEscuelaId]   = useState(null)
  const [tipoPrenda,  setTipoPrenda]  = useState(null)    // 'DEPORTIVO' | 'OFICIAL'
  const [genero,      setGenero]      = useState(null)    // 'NINA' | 'NINO' | 'COMPARTIDO'
  const [tipoPiezaId, setTipoPiezaId] = useState(null)

  // ── Datos ──
  const [options,     setOptions]     = useState(null)
  const [loadingOpts, setLoadingOpts] = useState(true)
  const [products,    setProducts]    = useState(null)
  const [loadingProd, setLoadingProd] = useState(false)

  // ── Search tab ──
  const [tab,         setTab]         = useState('guided') // 'guided' | 'search'
  const [q,           setQ]           = useState('')
  const [searchData,  setSearchData]  = useState(null)
  const [searchPage,  setSearchPage]  = useState(1)
  const [searchLoad,  setSearchLoad]  = useState(false)
  const searchDebounce = useRef(null)

  // ── Cart & nav ──
  const { client, lines, addLine } = useCart()
  const navigate = useNavigate()

  // Flash al agregar
  const [addedSku, setAddedSku] = useState(null)

  // ── Cargar opciones una sola vez ──────────────────────────────────────────
  useEffect(() => {
    setLoadingOpts(true)
    catalogApi.guidedOptions()
      .then(setOptions)
      .catch(() => {})
      .finally(() => setLoadingOpts(false))
  }, [])

  // ── Cargar productos cuando hay filtros suficientes ───────────────────────
  useEffect(() => {
    if (!mode) { setProducts(null); return }
    if (mode === 'school' && !escuelaId) { setProducts(null); return }

    setLoadingProd(true)
    catalogApi.guidedProducts({ mode, escuela_id: escuelaId, tipo_prenda: tipoPrenda, genero, tipo_pieza_id: tipoPiezaId })
      .then(setProducts)
      .catch(() => {})
      .finally(() => setLoadingProd(false))
  }, [mode, escuelaId, tipoPrenda, genero, tipoPiezaId])

  // ── Búsqueda libre ────────────────────────────────────────────────────────
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

  // ── Detail modal (search tab) ─────────────────────────────────────────────
  const [detail, setDetail] = useState(null)
  async function openDetail(id) {
    const prod = await catalogApi.get(id).catch(() => null)
    if (prod) setDetail(prod)
  }

  // ── Agregar al carrito ────────────────────────────────────────────────────
  function handleAdd(variante, nombre) {
    addLine(
      { sku: variante.sku, talla: variante.talla, color: variante.color, precio_venta: Number(variante.precio_venta) },
      { nombre }
    )
    setAddedSku(variante.sku)
    if (navigator.vibrate) navigator.vibrate(40)
    setTimeout(() => setAddedSku(null), 900)
  }

  // ── Datos derivados ───────────────────────────────────────────────────────
  const nivel = useMemo(
    () => options?.niveles.find(n => n.id === nivelId),
    [options, nivelId]
  )
  const escuela = useMemo(
    () => nivel?.escuelas.find(e => e.id === escuelaId),
    [nivel, escuelaId]
  )

  // Breadcrumb
  const crumbs = useMemo(() => {
    const items = []
    if (!mode) return items
    items.push({
      label: mode === 'school' ? '🏫 Uniformes' : '📦 Básicos',
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

  // Paso actual
  const step = useMemo(() => {
    if (!mode) return 'mode'
    if (mode === 'school' && !nivelId) return 'nivel'
    if (mode === 'school' && !escuelaId) return 'escuela'
    return 'products'
  }, [mode, nivelId, escuelaId])

  // Carrito
  const cartTotal = lines.reduce((acc, l) => acc + Number(l.subtotal), 0)

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-gray-50">

      {/* ── Header ── */}
      <div className="bg-white px-4 pt-4 pb-3 border-b border-gray-100 space-y-2 shrink-0">
        {/* Cliente activo */}
        {client && (
          <div className="flex items-center gap-2 bg-brand-50 rounded-xl px-3 py-2">
            <span className="text-brand-600 text-sm">👤</span>
            <span className="text-brand-800 text-sm font-medium flex-1 truncate">{client.nombre}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => setTab('guided')}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all
              ${tab === 'guided' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}
          >
            🗂 Guiado
          </button>
          <button
            onClick={() => setTab('search')}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all
              ${tab === 'search' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}
          >
            🔍 Buscar
          </button>
        </div>
      </div>

      {/* ══ TAB: BÚSQUEDA ══════════════════════════════════════════════════════ */}
      {tab === 'search' && (
        <>
          <div className="bg-white px-4 pb-3 border-b border-gray-100 shrink-0">
            <div className="relative">
              <input
                type="search"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Buscar producto, SKU o categoría…"
                className="w-full bg-gray-100 rounded-xl px-4 py-3 text-sm outline-none pl-9"
                autoFocus
              />
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-2">
            {searchLoad && <Spinner className="py-12" />}
            {!searchLoad && searchData?.items.map(p => (
              <button
                key={p.id}
                onClick={() => openDetail(p.id)}
                className="w-full bg-white rounded-2xl p-4 flex items-center gap-3 text-left shadow-sm active:scale-[0.99]"
              >
                <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-brand-600 shrink-0">👕</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{p.nombre}</p>
                  <p className="text-xs text-gray-500">{p.categoria} · {p.total_variantes} talla{p.total_variantes !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-brand-700">${fmt(p.precio_desde)}</p>
                  <p className="text-[10px] text-gray-400">desde</p>
                </div>
              </button>
            ))}
            {!searchLoad && searchData?.items.length === 0 && (
              <p className="text-center text-gray-400 py-12 text-sm">Sin resultados para "{q}"</p>
            )}
            {!searchLoad && searchData && searchData.total > searchData.page_size && (
              <div className="flex gap-2 pt-2 pb-4">
                <button disabled={searchPage === 1}
                  onClick={() => { const p = searchPage - 1; setSearchPage(p); runSearch(q, p) }}
                  className="flex-1 py-2 bg-white rounded-xl border border-gray-200 text-sm disabled:opacity-40">
                  ← Anterior
                </button>
                <button disabled={searchData.page * searchData.page_size >= searchData.total}
                  onClick={() => { const p = searchPage + 1; setSearchPage(p); runSearch(q, p) }}
                  className="flex-1 py-2 bg-white rounded-xl border border-gray-200 text-sm disabled:opacity-40">
                  Siguiente →
                </button>
              </div>
            )}
          </div>

          {/* Modal detalle (search) */}
          {detail && (
            <div className="fixed inset-0 z-50 flex items-end bg-black/50" onClick={() => setDetail(null)}>
              <div className="w-full bg-white rounded-t-3xl p-5 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 text-lg leading-tight">{detail.nombre}</h3>
                    <p className="text-sm text-gray-500">{detail.categoria} · {detail.marca}</p>
                  </div>
                  <button onClick={() => setDetail(null)} className="text-gray-400 text-3xl leading-none pl-3">×</button>
                </div>
                <div className="space-y-2">
                  {detail.variantes.map(v => (
                    <div key={v.id} className="flex items-center gap-3 bg-gray-50 rounded-xl p-3">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-800">{v.talla} · {v.color}</p>
                        <p className="text-xs text-gray-400">{v.sku}</p>
                      </div>
                      <p className="font-bold text-brand-700 mr-2">${fmt(v.precio_venta)}</p>
                      <button
                        onClick={() => handleAdd(v, detail.nombre)}
                        className={`shrink-0 px-4 py-2 rounded-xl font-semibold text-sm transition-all
                          ${addedSku === v.sku ? 'bg-green-500 text-white scale-95' : 'bg-brand-700 text-white active:bg-brand-800'}`}
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

      {/* ══ TAB: GUIADO ════════════════════════════════════════════════════════ */}
      {tab === 'guided' && (
        <>
          {/* Breadcrumb de navegación */}
          {crumbs.length > 0 && (
            <div className="bg-white px-4 py-2 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
                <button
                  onClick={crumbs[0].onClick}
                  className="shrink-0 text-brand-600 text-sm font-medium active:text-brand-800"
                >
                  ← Atrás
                </button>
                <span className="text-gray-300 mx-1">|</span>
                {crumbs.map((c, i) => (
                  <span key={i} className="flex items-center gap-1 shrink-0">
                    {i > 0 && <span className="text-gray-300 text-xs">›</span>}
                    <button
                      onClick={c.onClick}
                      className="text-sm text-gray-500 font-medium max-w-[120px] truncate active:text-brand-700"
                    >
                      {c.label}
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {loadingOpts && step === 'mode' && <Spinner className="flex-1" />}

          {/* ── Paso 0: elegir modo ── */}
          {step === 'mode' && !loadingOpts && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 gap-4">
              <p className="text-gray-500 text-sm mb-2">¿Qué tipo de productos?</p>
              <div className="w-full grid grid-cols-2 gap-4">
                <button
                  onClick={() => setMode('school')}
                  className="flex flex-col items-center gap-3 bg-white rounded-3xl p-6 shadow-sm
                    border-2 border-transparent active:border-brand-400 active:bg-brand-50 transition-all"
                >
                  <span className="text-5xl">🏫</span>
                  <span className="font-bold text-gray-800 text-center text-sm leading-tight">
                    Uniformes Escolares
                  </span>
                  {options && (
                    <span className="text-xs text-gray-400">
                      {options.niveles.length} niveles
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setMode('basics')}
                  className="flex flex-col items-center gap-3 bg-white rounded-3xl p-6 shadow-sm
                    border-2 border-transparent active:border-brand-400 active:bg-brand-50 transition-all"
                >
                  <span className="text-5xl">📦</span>
                  <span className="font-bold text-gray-800 text-center text-sm leading-tight">
                    Básicos
                  </span>
                  {options && (
                    <span className="text-xs text-gray-400">
                      {options.tipo_pieza_basics.length} tipos
                    </span>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ── Paso 1 (school): elegir nivel ── */}
          {step === 'nivel' && options && (
            <div className="flex-1 min-h-0 py-3">
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold px-4 mb-3">
                Nivel educativo
              </p>
              <StepList
                items={options.niveles}
                onSelect={n => setNivelId(n.id)}
                badgeFn={n => `${n.escuelas.length} escuela${n.escuelas.length !== 1 ? 's' : ''}`}
              />
            </div>
          )}

          {/* ── Paso 2 (school): elegir escuela ── */}
          {step === 'escuela' && nivel && (
            <div className="flex-1 min-h-0 py-3">
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold px-4 mb-3">
                Escuela — {nivel.nombre}
              </p>
              <StepList
                items={nivel.escuelas}
                onSelect={e => setEscuelaId(e.id)}
              />
            </div>
          )}

          {/* ── Paso 3+: productos con filtros inline ── */}
          {step === 'products' && (
            <div className="flex-1 min-h-0 flex flex-col">

              {/* Filtros inline: tipo_prenda, genero, tipo_pieza */}
              {(products?.tipo_prenda_options?.length > 0
                || products?.genero_options?.length > 0
                || products?.tipo_pieza_options?.length > 0
                || options?.tipo_pieza_basics?.length > 0
              ) && (
                <div className="bg-white border-b border-gray-100 px-4 py-3 shrink-0 space-y-2.5">
                  {/* Tipo de prenda (Deportivo / Oficial) — solo mode=school */}
                  {mode === 'school' && products?.tipo_prenda_options?.length > 0 && (
                    <FilterChips
                      options={products.tipo_prenda_options}
                      selected={tipoPrenda}
                      onSelect={val => { setTipoPrenda(val); setGenero(null) }}
                      labelFn={v => PRENDA_LABEL[v] ?? v}
                    />
                  )}

                  {/* Género — solo si hay más de una opción */}
                  {mode === 'school' && tipoPrenda && products?.genero_options?.length > 1 && (
                    <FilterChips
                      options={products.genero_options}
                      selected={genero}
                      onSelect={setGenero}
                      labelFn={v => GENERO_LABEL[v] ?? v}
                    />
                  )}

                  {/* Tipo de pieza */}
                  {(() => {
                    const piezaOpts = mode === 'school'
                      ? products?.tipo_pieza_options
                      : options?.tipo_pieza_basics
                    if (!piezaOpts?.length) return null
                    return (
                      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
                        <button
                          onClick={() => setTipoPiezaId(null)}
                          className={`shrink-0 px-4 py-2 rounded-full text-sm font-semibold transition-all
                            ${!tipoPiezaId ? 'bg-brand-700 text-white shadow-md shadow-brand-700/30' : 'bg-gray-100 text-gray-700'}`}
                        >
                          Todas
                        </button>
                        {piezaOpts.map(tp => (
                          <button
                            key={tp.id}
                            onClick={() => setTipoPiezaId(tipoPiezaId === tp.id ? null : tp.id)}
                            className={`shrink-0 px-4 py-2 rounded-full text-sm font-semibold transition-all
                              ${tipoPiezaId === tp.id
                                ? 'bg-brand-700 text-white shadow-md shadow-brand-700/30'
                                : 'bg-gray-100 text-gray-700 active:bg-gray-200'
                              }`}
                          >
                            {tp.nombre}
                          </button>
                        ))}
                      </div>
                    )
                  })()}
                </div>
              )}

              {/* Lista de familias */}
              <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-3">
                {loadingProd && <Spinner className="py-12" />}

                {!loadingProd && products?.families?.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <span className="text-4xl">🔍</span>
                    <p className="text-gray-500 text-sm text-center">
                      Sin productos para esta selección.
                      {mode === 'school' && !tipoPrenda && (
                        <> Selecciona un tipo de uniforme.</>
                      )}
                    </p>
                  </div>
                )}

                {!loadingProd && products?.families?.map(family => (
                  <FamilyCard
                    key={family.key}
                    family={family}
                    onAdd={handleAdd}
                    addedSku={addedSku}
                  />
                ))}

                {/* Basics: mostrar productos aunque no haya filtros aplicados aún */}
                {!loadingProd && mode === 'basics' && !products && !loadingProd && (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <Spinner />
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Carrito flotante ── */}
      {lines.length > 0 && (
        <div className="px-4 pb-2 shrink-0 bg-transparent">
          <button
            onClick={() => navigate('/quotes/current')}
            className="w-full bg-brand-700 text-white rounded-2xl px-4 py-4
              flex items-center justify-between shadow-lg active:bg-brand-800"
          >
            <span className="font-semibold">Ver presupuesto ({lines.length})</span>
            <span className="font-bold text-lg">${fmt(cartTotal)}</span>
          </button>
        </div>
      )}
    </div>
  )
}
