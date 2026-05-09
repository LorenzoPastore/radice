'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { verifyEmail } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

type Status = 'loading' | 'success' | 'error' | 'missing-token'

function VerifyEmailInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<Status>('loading')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setStatus('missing-token')
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const res = await verifyEmail(token)
        if (cancelled) return
        setStatus('success')
        setMessage(res.detail ?? 'Email verificata con successo.')
        setTimeout(() => {
          if (!cancelled) router.push('/login')
        }, 2000)
      } catch (err) {
        if (cancelled) return
        const msg =
          err instanceof ApiError
            ? (err.detail ?? 'Token non valido o scaduto.')
            : 'Errore di rete.'
        setStatus('error')
        setMessage(msg)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, router])

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Verifica email</CardTitle>
          <CardDescription>
            {status === 'loading' && 'Verifica in corso…'}
            {status === 'success' && 'Email verificata.'}
            {status === 'error' && 'Verifica non riuscita.'}
            {status === 'missing-token' && 'Token mancante.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status === 'loading' && (
            <p className="text-muted-foreground text-sm">
              Stiamo verificando il tuo indirizzo email…
            </p>
          )}
          {status === 'success' && (
            <p className="text-sm">
              {message} Verrai reindirizzato al login tra pochi
              istanti.
            </p>
          )}
          {status === 'error' && (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-destructive text-sm"
            >
              {message}
            </div>
          )}
          {status === 'missing-token' && (
            <p className="text-muted-foreground text-sm">
              Il link di verifica non contiene un token valido.
            </p>
          )}
        </CardContent>
        {(status === 'error' || status === 'missing-token') && (
          <CardFooter>
            <Button asChild className="w-full min-h-11">
              <Link href="/login">Vai al login</Link>
            </Button>
          </CardFooter>
        )}
      </Card>
    </main>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  )
}
