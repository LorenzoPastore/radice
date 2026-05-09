'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  confirmPasswordReset,
  requestPasswordReset,
} from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

function PasswordResetInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [email, setEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setIsLoading(true)
    try {
      const res = await requestPasswordReset(email)
      setSuccess(
        res.detail ??
          'Se l’email esiste, riceverai un link per reimpostare la password.',
      )
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.detail ?? 'Richiesta non riuscita.')
          : 'Errore di rete.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (newPassword !== confirmPassword) {
      setError('Le password non corrispondono.')
      return
    }
    if (!token) return
    setIsLoading(true)
    try {
      const res = await confirmPasswordReset(token, newPassword)
      setSuccess(
        res.detail ??
          'Password reimpostata. Verrai reindirizzato al login.',
      )
      setTimeout(() => router.push('/login'), 2000)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.detail ?? 'Token non valido o scaduto.')
          : 'Errore di rete.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  if (token) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Imposta nuova password</CardTitle>
            <CardDescription>
              Scegli una password sicura di almeno 8 caratteri.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleConfirm}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new_password">Nuova password</Label>
                <Input
                  id="new_password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Conferma password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              {error && (
                <div
                  role="alert"
                  className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-destructive text-sm"
                >
                  {error}
                </div>
              )}
              {success && (
                <div className="rounded-md border border-green-500/50 bg-green-500/10 p-3 text-green-700 text-sm dark:text-green-400">
                  {success}
                </div>
              )}
            </CardContent>
            <CardFooter className="flex flex-col gap-3">
              <Button
                type="submit"
                className="w-full min-h-11"
                disabled={isLoading}
              >
                {isLoading ? 'Salvataggio…' : 'Reimposta password'}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Recupera password</CardTitle>
          <CardDescription>
            Inserisci la tua email per ricevere un link di reset.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleRequest}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>
            {error && (
              <div
                role="alert"
                className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-destructive text-sm"
              >
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-md border border-green-500/50 bg-green-500/10 p-3 text-green-700 text-sm dark:text-green-400">
                {success}
              </div>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button
              type="submit"
              className="w-full min-h-11"
              disabled={isLoading}
            >
              {isLoading ? 'Invio…' : 'Invia link di reset'}
            </Button>
            <Link
              href="/login"
              className="text-center text-muted-foreground text-sm underline-offset-4 hover:underline"
            >
              Torna al login
            </Link>
          </CardFooter>
        </form>
      </Card>
    </main>
  )
}

export default function PasswordResetPage() {
  return (
    <Suspense fallback={null}>
      <PasswordResetInner />
    </Suspense>
  )
}
