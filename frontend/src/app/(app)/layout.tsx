// TODO(Milestone 1): Add auth guard — redirect to /login if no session
export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
