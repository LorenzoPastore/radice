'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api/client'
import {
  changePassword,
  updateMe,
  updateMePerson,
} from '@/lib/api/me'
import type {
  DatePrecision,
  Gender,
  PrivacyPreset,
} from '@/lib/api/types'
import { useAuthStore } from '@/stores/authStore'

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.detail) return err.detail
    if (err.fieldErrors) {
      const first = Object.entries(err.fieldErrors)[0]
      if (first) {
        const [field, msgs] = first
        return `${field}: ${
          Array.isArray(msgs) ? msgs.join(', ') : String(msgs)
        }`
      }
    }
  }
  return fallback
}

export default function ProfileSettingsPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const person = useAuthStore((s) => s.person)
  const refresh = useAuthStore((s) => s.refresh)
  const logout = useAuthStore((s) => s.logout)
  const setUser = useAuthStore((s) => s.setUser)
  const setPerson = useAuthStore((s) => s.setPerson)

  const [hydrated, setHydrated] = useState(false)

  // Account fields
  const [displayName, setDisplayName] = useState('')
  const [locale, setLocale] = useState('it')
  const [timezone, setTimezone] = useState('Europe/Rome')
  const [privacyPreset, setPrivacyPreset] =
    useState<PrivacyPreset>('balanced')
  const [savingAccount, setSavingAccount] = useState(false)

  // Person fields
  const [givenNames, setGivenNames] = useState('')
  const [surname, setSurname] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [birthDatePrecision, setBirthDatePrecision] =
    useState<DatePrecision>('exact')
  const [birthPlace, setBirthPlace] = useState('')
  const [gender, setGender] = useState<Gender>('unknown')
  const [shortBio, setShortBio] = useState('')
  const [savingPerson, setSavingPerson] = useState(false)

  // Password fields
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)

  const [loggingOut, setLoggingOut] = useState(false)

  useEffect(() => {
    refresh()
      .then(() => setHydrated(true))
      .catch(() => router.push('/login'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? '')
      setLocale(user.locale ?? 'it')
      setTimezone(user.timezone ?? 'Europe/Rome')
      setPrivacyPreset(user.privacy_preset ?? 'balanced')
    }
  }, [user])

  useEffect(() => {
    if (person) {
      setGivenNames(person.given_names ?? '')
      setSurname(person.surname ?? '')
      setBirthDate(person.birth_date ?? '')
      setBirthDatePrecision(person.birth_date_precision ?? 'exact')
      setBirthPlace(person.birth_place ?? '')
      setGender(person.gender ?? 'unknown')
      setShortBio(person.short_bio ?? '')
    }
  }, [person])

  async function handleSaveAccount(e: React.FormEvent) {
    e.preventDefault()
    setSavingAccount(true)
    try {
      const res = await updateMe({
        display_name: displayName,
        locale,
        timezone,
        privacy_preset: privacyPreset,
      })
      setUser(res.user)
      toast.success('Account aggiornato.')
    } catch (err) {
      toast.error(errorMessage(err, 'Aggiornamento non riuscito.'))
    } finally {
      setSavingAccount(false)
    }
  }

  async function handleSavePerson(e: React.FormEvent) {
    e.preventDefault()
    setSavingPerson(true)
    try {
      const res = await updateMePerson({
        given_names: givenNames,
        surname,
        birth_date: birthDate || null,
        birth_date_precision: birthDatePrecision,
        birth_place: birthPlace || null,
        gender,
        short_bio: shortBio || null,
      })
      setPerson(res)
      toast.success('Profilo aggiornato.')
    } catch (err) {
      toast.error(errorMessage(err, 'Aggiornamento non riuscito.'))
    } finally {
      setSavingPerson(false)
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    if (newPassword !== confirmNewPassword) {
      toast.error('Le nuove password non corrispondono.')
      return
    }
    setSavingPassword(true)
    try {
      await changePassword(currentPassword, newPassword)
      toast.success('Password aggiornata.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmNewPassword('')
    } catch (err) {
      toast.error(errorMessage(err, 'Cambio password non riuscito.'))
    } finally {
      setSavingPassword(false)
    }
  }

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      router.push('/login')
    }
  }

  if (!hydrated) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <p className="text-muted-foreground text-sm">Caricamento…</p>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-4 pb-24">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-bold text-2xl tracking-tight">
            Impostazioni profilo
          </h1>
          {user && (
            <p className="text-muted-foreground text-sm">
              {user.email}
            </p>
          )}
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={handleLogout}
          disabled={loggingOut}
          className="min-h-11"
        >
          {loggingOut ? 'Uscita…' : 'Logout'}
        </Button>
      </header>

      {/* Account */}
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>
            Preferenze utente e privacy.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSaveAccount}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="display_name">Nome visualizzato</Label>
              <Input
                id="display_name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={savingAccount}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="locale">Lingua</Label>
                <Input
                  id="locale"
                  type="text"
                  value={locale}
                  onChange={(e) => setLocale(e.target.value)}
                  disabled={savingAccount}
                  placeholder="it"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">Fuso orario</Label>
                <Input
                  id="timezone"
                  type="text"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  disabled={savingAccount}
                  placeholder="Europe/Rome"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="privacy_preset">Privacy</Label>
              <select
                id="privacy_preset"
                value={privacyPreset}
                onChange={(e) =>
                  setPrivacyPreset(e.target.value as PrivacyPreset)
                }
                disabled={savingAccount}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="reserved">Riservato</option>
                <option value="balanced">Bilanciato</option>
                <option value="open">Aperto</option>
                <option value="custom">Personalizzato</option>
              </select>
            </div>
          </CardContent>
          <CardFooter>
            <Button
              type="submit"
              className="min-h-11"
              disabled={savingAccount}
            >
              {savingAccount ? 'Salvataggio…' : 'Salva account'}
            </Button>
          </CardFooter>
        </form>
      </Card>

      {/* Person */}
      <Card>
        <CardHeader>
          <CardTitle>Profilo</CardTitle>
          <CardDescription>
            Informazioni anagrafiche associate al tuo profilo nel
            sistema.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSavePerson}>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="given_names">Nome</Label>
                <Input
                  id="given_names"
                  type="text"
                  value={givenNames}
                  onChange={(e) => setGivenNames(e.target.value)}
                  disabled={savingPerson}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="surname">Cognome</Label>
                <Input
                  id="surname"
                  type="text"
                  value={surname}
                  onChange={(e) => setSurname(e.target.value)}
                  disabled={savingPerson}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="birth_date">Data di nascita</Label>
                <Input
                  id="birth_date"
                  type="date"
                  value={birthDate}
                  onChange={(e) => setBirthDate(e.target.value)}
                  disabled={savingPerson}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="birth_date_precision">
                  Precisione data
                </Label>
                <select
                  id="birth_date_precision"
                  value={birthDatePrecision}
                  onChange={(e) =>
                    setBirthDatePrecision(
                      e.target.value as DatePrecision,
                    )
                  }
                  disabled={savingPerson}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="exact">Esatta</option>
                  <option value="month">Mese</option>
                  <option value="year">Anno</option>
                  <option value="decade">Decennio</option>
                  <option value="unknown">Sconosciuta</option>
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="birth_place">Luogo di nascita</Label>
              <Input
                id="birth_place"
                type="text"
                value={birthPlace}
                onChange={(e) => setBirthPlace(e.target.value)}
                disabled={savingPerson}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gender">Genere</Label>
              <select
                id="gender"
                value={gender}
                onChange={(e) => setGender(e.target.value as Gender)}
                disabled={savingPerson}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="unknown">Non specificato</option>
                <option value="female">Femmina</option>
                <option value="male">Maschio</option>
                <option value="non_binary">Non binario</option>
                <option value="other">Altro</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="short_bio">Bio breve</Label>
              <textarea
                id="short_bio"
                value={shortBio}
                onChange={(e) => setShortBio(e.target.value)}
                disabled={savingPerson}
                rows={4}
                className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button
              type="submit"
              className="min-h-11"
              disabled={savingPerson}
            >
              {savingPerson ? 'Salvataggio…' : 'Salva profilo'}
            </Button>
          </CardFooter>
        </form>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <CardTitle>Sicurezza</CardTitle>
          <CardDescription>Cambia la tua password.</CardDescription>
        </CardHeader>
        <form onSubmit={handleChangePassword}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current_password">Password attuale</Label>
              <Input
                id="current_password"
                type="password"
                required
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                disabled={savingPassword}
              />
            </div>
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
                disabled={savingPassword}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm_new_password">
                Conferma nuova password
              </Label>
              <Input
                id="confirm_new_password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirmNewPassword}
                onChange={(e) =>
                  setConfirmNewPassword(e.target.value)
                }
                disabled={savingPassword}
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button
              type="submit"
              className="min-h-11"
              disabled={savingPassword}
            >
              {savingPassword ? 'Salvataggio…' : 'Cambia password'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </main>
  )
}
