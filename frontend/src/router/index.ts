import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            component: () => import('@/layout/index.vue'),
            redirect: '/rss',
            children: [
                {
                    path: '/rss',
                    name: 'RssManagement',
                    component: () => import('@/views/rss/Index.vue'),
                    meta: { title: 'RSS 源管理', icon: 'Connection' },
                },
                {
                    path: '/dashboard',
                    name: 'Dashboard',
                    component: () => import('@/views/dashboard/Index.vue'),
                    meta: { title: '任务监控', icon: 'Monitor' },
                },
            ],
        },
    ],
})

export default router
