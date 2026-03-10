<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item">
            <el-icon :size="40" color="#409eff"><Connection /></el-icon>
            <div class="stat-info">
              <span class="stat-value">{{ stats.totalSources }}</span>
              <span class="stat-label">RSS 源总数</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item">
            <el-icon :size="40" color="#67c23a"><CircleCheck /></el-icon>
            <div class="stat-info">
              <span class="stat-value">{{ stats.activeSources }}</span>
              <span class="stat-label">启用中</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item">
            <el-icon :size="40" color="#e6a23c"><Warning /></el-icon>
            <div class="stat-info">
              <span class="stat-value">{{ stats.inactiveSources }}</span>
              <span class="stat-label">已禁用</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 手动触发采集按钮 -->
    <el-card shadow="never" style="margin-top: 20px">
      <template #header>
        <div class="trigger-header">
          <span>🚀 内容采集与生成</span>
        </div>
      </template>
      <div class="trigger-area">
        <p class="trigger-desc">
          点击下方按钮，系统将自动从所有已启用的 RSS 源抓取最新新闻，并调用 AI 大模型生成多平台文案（公众号 + 小红书），生成结果将保存到本地存档目录。
        </p>
        <el-button
          type="primary"
          size="large"
          :icon="Promotion"
          :loading="collecting"
          @click="handleTrigger"
        >
          {{ collecting ? '正在采集生成中...' : '手动触发采集生成' }}
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 20px">
      <template #header>
        <span>📋 系统状态</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="系统版本">v1.1.0</el-descriptions-item>
        <el-descriptions-item label="后端状态">
          <el-tag :type="backendOnline ? 'success' : 'danger'" size="small">
            {{ backendOnline ? '在线' : '离线' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="数据库">SQLite</el-descriptions-item>
        <el-descriptions-item label="AI 模型">OpenAI 兼容接口</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { fetchRssSources } from '@/api/rss'
import { triggerCollection } from '@/api/tasks'
import request from '@/utils/request'

const stats = reactive({
  totalSources: 0,
  activeSources: 0,
  inactiveSources: 0,
})

const backendOnline = ref(false)
const collecting = ref(false)

async function handleTrigger() {
  collecting.value = true
  try {
    const res = await triggerCollection()
    ElMessage.success(res.message || '采集生成任务已触发，请在后台日志中查看进度')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    collecting.value = false
  }
}

onMounted(async () => {
  try {
    const sources = await fetchRssSources()
    stats.totalSources = sources.length
    stats.activeSources = sources.filter((s) => s.is_active).length
    stats.inactiveSources = stats.totalSources - stats.activeSources
  } catch { /* ignore */ }

  try {
    const res = await request.get<any, { status: string }>('/health')
    backendOnline.value = res?.status === 'ok'
  } catch {
    backendOnline.value = false
  }
})
</script>

<style scoped>
.dashboard {
  max-width: 1000px;
}

.stat-card {
  cursor: default;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 8px 0;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

.trigger-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.trigger-area {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}

.trigger-desc {
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
</style>
