'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { resendVerification } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'
import { useAuthStore } from '@/stores/authStore'

function VerifyEmailPendingInner() {
  const searchParams = useSearchParams()
  const email = searchParams.get('email')
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [isSending, setIsSending] = useState(false)

  async function handleResend() {
    setIsSending(true)
    try {
      await resendVerification()
      toast.success('Email di verifica inviata.')
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? (err.detail ?? 'Impossibile reinviare ora.')
          : 'Errore di rete.'
      toast.error(msg)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Controlla la tua email</CardTitle>
          <CardDescription>
            {email ? (
              <>
                Abbiamo inviato un link di verifica a{' '}
                <strong>{email}</strong>.
              </>
            ) : (
              <>Abbiamo inviato un link di verifica al tuo indirizzo.</>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Clicca il link nell&apos;email per attivare il tuo account.
            Controlla anche la cartella spam.
          </p>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          {isAuthenticated && (
            <Button
              type="button"
              variant="outline"
              className="w-full min-h-11"
              onClick={handleResend}
              disabled={isSending}
            >
              {isSending ? 'Invio…' : 'Reinvia email'}
            </Button>
          )}
          <Link
            href="/login"
            className="text-center text-muted-foreground text-sm underline-offset-4 hover:underline"
          >
            Torna al login
          </Link>
        </CardFooter>
      </Card>
    </main>
  )
}

export default function VerifyEmailPendingPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailPendingInner />
    </Suspense>
  )
}
