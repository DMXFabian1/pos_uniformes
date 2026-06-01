import { useRef, useState, useCallback } from 'react'

const THRESHOLD = 60

export default function PullToRefresh({ onRefresh, children, className = '' }) {
  const containerRef = useRef(null)
  const startY = useRef(0)
  const [pullY, setPullY] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const pulling = useRef(false)

  const onTouchStart = useCallback((e) => {
    if (refreshing) return
    const el = containerRef.current
    if (el && el.scrollTop <= 0) {
      startY.current = e.touches[0].clientY
      pulling.current = true
    }
  }, [refreshing])

  const onTouchMove = useCallback((e) => {
    if (!pulling.current || refreshing) return
    const dy = e.touches[0].clientY - startY.current
    if (dy > 0) {
      setPullY(Math.min(dy * 0.4, 80))
    } else {
      pulling.current = false
      setPullY(0)
    }
  }, [refreshing])

  const onTouchEnd = useCallback(async () => {
    if (!pulling.current) return
    pulling.current = false
    if (pullY >= THRESHOLD && onRefresh) {
      setRefreshing(true)
      setPullY(50)
      try { await onRefresh() } finally {
        setRefreshing(false)
        setPullY(0)
      }
    } else {
      setPullY(0)
    }
  }, [pullY, onRefresh])

  return (
    <div
      ref={containerRef}
      className={`overflow-y-auto overscroll-contain ${className}`}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <div
        className="flex items-center justify-center overflow-hidden transition-all"
        style={{ height: pullY, opacity: pullY / THRESHOLD }}
      >
        <div className={`w-6 h-6 rounded-full border-[2.5px] border-surface-200 border-t-brand-500 ${refreshing ? 'animate-spin' : ''}`}
          style={{ transform: refreshing ? 'none' : `rotate(${pullY * 3}deg)` }}
        />
      </div>
      {children}
    </div>
  )
}
