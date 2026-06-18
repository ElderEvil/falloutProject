# Auth

Authentication and user management module. Handles login, registration, password reset flows, and email verification with terminal-themed form components and Pinia-backed state management.

## Routes

- `/login` — LoginFormTerminal
- `/register` — RegisterForm
- `/forgot-password` — ForgotPasswordView
- `/reset-password` — ResetPasswordView
- `/verify-email` — VerifyEmailView

## Key Files

- `components/LoginFormTerminal.vue` — terminal-styled login form
- `components/RegisterForm.vue` — user registration form
- `views/ForgotPasswordView.vue` — password reset request view
- `views/ResetPasswordView.vue` — password reset confirmation view
- `views/VerifyEmailView.vue` — email verification view
- `stores/auth.ts` — authentication state management
- `services/` — API service layer for auth operations
- `schemas/` — Zod validation schemas for auth forms
