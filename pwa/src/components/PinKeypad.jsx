export default function PinKeypad({ value, onChange, onSubmit, loading }) {
  const dots = Array.from({ length: 6 }, (_, i) => i < value.length ? 'filled' : 'empty')

  function press(digit) {
    if (value.length >= 8) return
    onChange(value + digit)
  }

  function del() {
    onChange(value.slice(0, -1))
  }

  const keys = ['1','2','3','4','5','6','7','8','9','','0','del']

  return (
    <div className="w-full max-w-[280px] mx-auto select-none">
      <div className="flex justify-center gap-3.5 mb-8">
        {dots.map((d, i) => (
          <div
            key={i}
            className={`w-3.5 h-3.5 rounded-full transition-all duration-200
              ${d === 'filled'
                ? 'bg-brand-600 scale-110'
                : 'bg-surface-300 border-2 border-surface-400'
              }`}
          />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {keys.map((k, i) => {
          if (k === '') return <div key={i} />
          if (k === 'del') return (
            <button
              key={i}
              onPointerDown={() => del()}
              className="h-[56px] rounded-2xl bg-surface-100 active:bg-surface-200 flex items-center justify-center text-ink-500 transition-all active:scale-95 touch-target"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9.75L14.25 12m0 0l2.25 2.25M14.25 12l2.25-2.25M14.25 12L12 14.25m-2.58 4.92l-6.374-6.375a1.125 1.125 0 010-1.59L9.42 4.83c.211-.211.498-.33.796-.33H19.5a2.25 2.25 0 012.25 2.25v10.5a2.25 2.25 0 01-2.25 2.25h-9.284c-.298 0-.585-.119-.796-.33z" />
              </svg>
            </button>
          )
          return (
            <button
              key={k}
              onPointerDown={() => press(k)}
              className="h-[56px] rounded-2xl bg-surface-0 border border-surface-300 active:bg-brand-50 active:border-brand-300
                flex items-center justify-center text-xl font-semibold text-ink-900 shadow-card transition-all active:scale-95 touch-target"
            >
              {k}
            </button>
          )
        })}
      </div>

      <button
        onClick={onSubmit}
        disabled={value.length < 4 || loading}
        className="mt-6 w-full h-[52px] btn-primary text-base"
      >
        {loading ? 'Entrando...' : 'Entrar'}
      </button>
    </div>
  )
}
