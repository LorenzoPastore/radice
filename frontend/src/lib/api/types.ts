export type DatePrecision = 'exact' | 'month' | 'year' | 'decade' | 'unknown'
export type Gender = 'male' | 'female' | 'non_binary' | 'unknown' | 'other'
export type PrivacyPreset = 'reserved' | 'balanced' | 'open' | 'custom'

export type User = {
  id: string
  email: string
  display_name: string
  email_verified_at: string | null
  locale: string
  timezone: string
  privacy_preset: PrivacyPreset
  notification_preferences: Record<string, unknown>
  created_at: string
}

export type Person = {
  id: string
  given_names: string
  surname: string
  surname_at_birth: string | null
  nicknames: string[]
  is_living: boolean
  birth_date: string | null
  birth_date_precision: DatePrecision
  birth_place: string | null
  death_date: string | null
  death_date_precision: DatePrecision
  death_place: string | null
  gender: Gender
  short_bio: string | null
  is_claimed: boolean
  created_at: string
  updated_at: string
}

export type LoginResponse = {
  token: string
  user: User
  email_verified: boolean
}

export type MeResponse = {
  user: User
  person: Person | null
}
