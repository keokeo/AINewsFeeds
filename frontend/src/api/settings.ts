import request from '@/utils/request'

/** 获取所有系统配置（按分类分组） */
export function fetchSettings(category?: string) {
    const params = category ? { category } : {}
    return request.get<any, Record<string, Record<string, { value: string; description: string }>>>(
        '/settings/',
        { params }
    )
}

/** 批量更新配置 */
export function updateSettings(configs: Record<string, string>) {
    return request.put<any, { message: string; updated_keys: string[] }>('/settings/', { configs })
}
