import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md space-y-6 text-center">
        <h1 className="font-bold text-4xl tracking-tight">Radice</h1>
        <p className="text-lg text-muted-foreground">
          La memoria della tua famiglia, preservata per sempre.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <Button asChild className="min-h-11">
            <Link href="/register">Crea account</Link>
          </Button>
          <Button asChild variant="outline" className="min-h-11">
            <Link href="/login">Accedi</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
