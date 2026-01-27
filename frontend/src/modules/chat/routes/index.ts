import type { RouteRecordRaw } from 'vue-router'

const DwellerChatPage = () => import('../components/DwellerChatPage.vue')

export const chatRoutes: RouteRecordRaw[] = [
  {
    path: '/dweller/:id/chat',
    name: 'DwellerChatPage',
    component: DwellerChatPage,
  },
]

export default chatRoutes
