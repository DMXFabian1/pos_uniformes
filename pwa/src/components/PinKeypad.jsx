/**
 * Teclado numerico grande para ingreso de PIN en pantallas tactiles.
 */
export default function PinKeypad({ value, onChange, onSubmit, loading }) {
  const dots = Array.from({ length: 6 }, (_, i) => i < value.length ? '●' : '○')

  function press(digit) {
    if (value.length >= 8) return
    onChange(value + digit)
  }

  function del() {
    onChange(value.slice(0, -1))
  }

  const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫']

  return (
    <div className="w-full max-w-xs mx-auto select-none">
      {/* Indicador de PIN */}
      <div className="flex justify-center gap-3 mb-6">
        {dots.map((d, i) => (
          <span key={i} className={`text-2xl transition-all duration-100 ${d === '●' ? 'text-brand-700' : 'text-gray-300'}`}>
            {d}
          </span>
        ))}
      </div>

      {/* Teclado */}
      <div className="grid grid-cols-3 gap-3">
        {keys.map((k, i) => {
          if (k === '') return <div key={i} />
          if (k === '⌫') return (
            <button
              key={i}
              onPointerDown={() => del()}
              className="h-16 rounded-2xl bg-gray-100 active:bg-gray-200 flex items-center justify-center text-2xl text-gray-600 font-light transition-colors"
            >
              {k}
            </button>
          )
          return (
            <button
              key={k}
              onPointerDown={() => press(k)}
              className="h-16 rounded-2xl bg-white border border-gray-200 active:bg-brand-50 active:border-brand-300 flex items-center justify-center text-2xl font-medium text-gray-800 shadow-sm transition-colors"
            >
              {k}
            </button>
          )
        })}
      </div>

      {/* Boton entrar */}
      <button
        onClick={onSubmit}
        disabled={value.length < 4 || loading}
        className="mt-5 w-full h-14 rounded-2xl bg-brand-700 text-white font-semibold text-lg active:bg-brand-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow"
      >
        {loading ? 'Entrando…' : 'Entrar'}
      </button>
    </div>
  )
}
