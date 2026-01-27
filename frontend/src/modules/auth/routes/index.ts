import type { RouteRecordRaw } from 'vue-router'

const LoginPage = () => import('../components/LoginFormTerminal.vue')
const RegisterPage = () => import('../components/RegisterForm.vue')
const ForgotPasswordView = () => import('../views/ForgotPasswordView.vue')
const ResetPasswordView = () => import('../views/ResetPasswordView.vue')
const VerifyEmailView = () => import('../views/VerifyEmailView.vue')

export const authRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { hideFromNav: true },
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterPage,
    meta: { hideFromNav: true },
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: ForgotPasswordView,
    meta: { hideFromNav: true },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: ResetPasswordView,
    meta: { hideFromNav: true },
  },
  {
    path: '/verify-email',
    name: 'verify-email',
    component: VerifyEmailView,
    meta: { hideFromNav: true },
  },
]

export default authRoutes
