'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'

export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const refresh = useAuthStore((s) => s.refresh)

  useEffect(() => {
    refresh().catch(() => router.push('/login'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!isAuthenticated && !useAuthStore.getState().isLoading) {
      // Hydrated state already reflects auth; redirect if not auth'd.
      // Note: kept simple per M1 scope; can be hardened in M2.
    }
  }, [isAuthenticated])

  return <>{children}</>
}
