import request from '@/utils/request'

export interface RssSource {
    id: number
    name: string
    url: string
    is_active: boolean
    category: string
    retry_times: number
    fetch_interval: number
    description: string
    created_at: string
    updated_at: string
}

export interface RssSourceForm {
    name: string
    url: string
    is_active: boolean
    category: string
    retry_times: number
    fetch_interval: number
    description: string
}

/** 获取 RSS 源列表 */
export function fetchRssSources(params?: {
    is_active?: boolean
    category?: string
    keyword?: string
}) {
    return request.get<any, RssSource[]>('/rss/sources', { params })
}

/** 新增 RSS 源 */
export function createRssSource(data: RssSourceForm) {
    return request.post<any, RssSource>('/rss/sources', data)
}

/** 更新 RSS 源 */
export function updateRssSource(id: number, data: Partial<RssSourceForm>) {
    return request.put<any, RssSource>(`/rss/sources/${id}`, data)
}

/** 删除 RSS 源 */
export function deleteRssSource(id: number) {
    return request.delete(`/rss/sources/${id}`)
}
