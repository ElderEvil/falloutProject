# Profile

User profile, settings, and preferences module. Manages user account information, application settings, theme preferences, changelog viewing, and AI usage tracking.

## Routes

- `/profile` — ProfileView
- `/settings` — SettingsView
- `/preferences` — PreferencesView
- `/changelog` — ChangelogView

## Key Files

- `views/ProfileView.vue` — user profile overview
- `views/SettingsView.vue` — application settings page
- `views/PreferencesView.vue` — user preferences page
- `views/ChangelogView.vue` — version changelog display
- `stores/profile.ts` — profile state management
- `components/ProfileEditor.vue` — profile editing form
- `components/ProfileStats.vue` — profile statistics display
- `components/AIUsageCard.vue` — AI usage statistics card
- `components/ChangelogModal.vue` — changelog detail modal
- `models/` — profile type definitions
- `types/` — additional TypeScript type declarations
