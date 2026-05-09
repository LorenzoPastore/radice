import { apiRequest } from './client'
import type { MeResponse, Person, User } from './types'

export async function getMe(): Promise<MeResponse> {
  return apiRequest('/api/me/')
}

export async function updateMe(
  data: Partial<
    Pick<
      User,
      | 'display_name'
      | 'locale'
      | 'timezone'
      | 'privacy_preset'
      | 'notification_preferences'
    >
  >,
): Promise<MeResponse> {
  return apiRequest('/api/me/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function updateMePerson(
  data: Partial<
    Omit<
      Person,
      | 'id'
      | 'is_living'
      | 'is_claimed'
      | 'created_at'
      | 'updated_at'
      | 'death_date'
      | 'death_date_precision'
      | 'death_place'
    >
  >,
): Promise<Person> {
  return apiRequest('/api/me/person/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function changePassword(
  current_password: string,
  new_password: string,
): Promise<{ detail: string }> {
  return apiRequest('/api/me/change-password/', {
    method: 'POST',
    body: JSON.stringify({ current_password, new_password }),
  })
}
