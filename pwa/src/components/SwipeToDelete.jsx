import { useRef, useState } from 'react'

const THRESHOLD = 80
const DELETE_WIDTH = 80

export default function SwipeToDelete({ children, onDelete }) {
  const startX = useRef(0)
  const [offsetX, setOffsetX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const [open, setOpen] = useState(false)

  function onTouchStart(e) {
    startX.current = e.touches[0].clientX
    setSwiping(true)
  }

  function onTouchMove(e) {
    if (!swiping) return
    const dx = e.touches[0].clientX - startX.current
    if (open) {
      const next = Math.min(0, Math.max(-DELETE_WIDTH, -DELETE_WIDTH + dx))
      setOffsetX(next)
    } else {
      const next = Math.min(0, dx)
      setOffsetX(next)
    }
  }

  function onTouchEnd() {
    setSwiping(false)
    if (offsetX < -THRESHOLD) {
      setOffsetX(-DELETE_WIDTH)
      setOpen(true)
    } else {
      setOffsetX(0)
      setOpen(false)
    }
  }

  function handleDelete() {
    setOffsetX(-500)
    setTimeout(() => onDelete(), 200)
  }

  return (
    <div className="relative overflow-hidden rounded-2xl">
      <div
        className="absolute right-0 top-0 bottom-0 flex items-center justify-center bg-danger-500"
        style={{ width: DELETE_WIDTH }}
      >
        <button
          onClick={handleDelete}
          className="w-full h-full flex flex-col items-center justify-center text-white gap-0.5"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
          <span className="text-[10px] font-semibold">Eliminar</span>
        </button>
      </div>

      <div
        className="relative bg-surface-0 z-10"
        style={{
          transform: `translateX(${offsetX}px)`,
          transition: swiping ? 'none' : 'transform 0.25s cubic-bezier(0.32, 0.72, 0, 1)',
        }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        {children}
      </div>
    </div>
  )
}
