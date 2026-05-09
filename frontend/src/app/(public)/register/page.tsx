'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
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
import { register } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [givenNames, setGivenNames] = useState('')
  const [surname, setSurname] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIsLoading(true)
    try {
      await register({
        email,
        password,
        given_names: givenNames,
        surname,
        ...(displayName ? { display_name: displayName } : {}),
      })
      router.push(
        `/verify-email-pending?email=${encodeURIComponent(email)}`,
      )
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.detail) {
          setError(err.detail)
        } else if (err.fieldErrors) {
          const first = Object.entries(err.fieldErrors)[0]
          if (first) {
            const [field, msgs] = first
            setError(
              `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : String(msgs)}`,
            )
          } else {
            setError('Errore durante la registrazione.')
          }
        } else {
          setError('Errore durante la registrazione.')
        }
      } else {
        setError('Errore di rete. Riprova.')
      }
      setIsLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Crea il tuo account</CardTitle>
          <CardDescription>
            Inizia a costruire la memoria della tua famiglia.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="given_names">Nome</Label>
              <Input
                id="given_names"
                type="text"
                required
                autoComplete="given-name"
                value={givenNames}
                onChange={(e) => setGivenNames(e.target.value)}
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="surname">Cognome</Label>
              <Input
                id="surname"
                type="text"
                required
                autoComplete="family-name"
                value={surname}
                onChange={(e) => setSurname(e.target.value)}
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="display_name">
                Nome visualizzato{' '}
                <span className="text-muted-foreground text-xs">
                  (opzionale)
                </span>
              </Label>
              <Input
                id="display_name"
                type="text"
                autoComplete="nickname"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isLoading}
              />
            </div>
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
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
              <p className="text-muted-foreground text-xs">
                Almeno 8 caratteri.
              </p>
            </div>
            {error && (
              <div
                role="alert"
                className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-destructive text-sm"
              >
                {error}
              </div>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button
              type="submit"
              className="w-full min-h-11"
              disabled={isLoading}
            >
              {isLoading ? 'Creazione account…' : 'Crea account'}
            </Button>
            <p className="text-center text-muted-foreground text-sm">
              Hai già un account?{' '}
              <Link
                href="/login"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                Accedi
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </main>
  )
}
