import request from '@/utils/request'

/** 手动触发采集生成任务 */
export function triggerCollection() {
    return request.post<any, { message: string }>('/tasks/trigger')
}
