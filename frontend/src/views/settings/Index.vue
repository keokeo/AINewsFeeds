<template>
  <div class="settings-page" v-loading="loading">
    <!-- AI 模型配置 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header">
          <span>🤖 AI 模型配置</span>
          <el-tag size="small" type="info" effect="plain">ai</el-tag>
        </div>
      </template>
      <el-form label-width="160px" label-position="right">
        <el-form-item label="API Key">
          <el-input
            v-model="form.ai_api_key"
            placeholder="请输入大模型 API Key"
            show-password
            style="max-width: 480px"
          />
          <div class="form-hint">如使用火山引擎，请填写对应平台的 API Key</div>
        </el-form-item>
        <el-form-item label="API 地址 (Base URL)">
          <el-input
            v-model="form.ai_base_url"
            placeholder="https://api.openai.com/v1"
            style="max-width: 480px"
          />
          <div class="form-hint">兼容 OpenAI 接口协议的 API 地址</div>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input
            v-model="form.ai_model_name"
            placeholder="gpt-4o-mini"
            style="max-width: 320px"
          />
          <div class="form-hint">如 gpt-4o-mini、claude-3-sonnet 或火山引擎的 Endpoint ID</div>
        </el-form-item>
        <el-form-item label="Temperature">
          <div class="slider-row">
            <el-slider
              v-model="temperatureValue"
              :min="0"
              :max="100"
              :step="5"
              style="width: 300px"
            />
            <el-tag type="primary" size="large" effect="plain" class="temp-tag">
              {{ (temperatureValue / 100).toFixed(2) }}
            </el-tag>
          </div>
          <div class="form-hint">值越低越精确稳定，值越高越有创意和随机性</div>
        </el-form-item>
        <el-form-item label="系统提示词 (System Prompt)">
          <el-input
            v-model="form.ai_system_prompt"
            type="textarea"
            :rows="8"
            placeholder="你是一位资深的 AI 科技媒体主编..."
            style="max-width: 600px"
          />
          <div class="form-hint">设定大模型的角色和写作风格，影响生成内容的质量</div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 采集设置 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header">
          <span>📡 采集设置</span>
          <el-tag size="small" type="success" effect="plain">fetch</el-tag>
        </div>
      </template>
      <el-form label-width="160px" label-position="right">
        <el-form-item label="抓取时间范围（小时）">
          <el-input-number v-model.number="fetchHoursAgo" :min="1" :max="168" />
          <div class="form-hint">仅抓取过去 N 小时内发布的新闻</div>
        </el-form-item>
        <el-form-item label="摘要最大长度">
          <el-input-number v-model.number="fetchMaxSummary" :min="100" :max="2000" :step="100" />
          <div class="form-hint">每条新闻摘要截取的最大字符数</div>
        </el-form-item>
        <el-form-item label="最大分析新闻数">
          <el-input-number v-model.number="fetchMaxNews" :min="1" :max="50" />
          <div class="form-hint">每次最多传给大模型分析的新闻条数</div>
        </el-form-item>
        <el-form-item label="请求超时（秒）">
          <el-input-number v-model.number="fetchTimeout" :min="5" :max="60" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 推送设置 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header">
          <span>🚀 推送设置</span>
          <el-tag size="small" type="warning" effect="plain">push</el-tag>
        </div>
      </template>
      <el-form label-width="160px" label-position="right">
        <el-form-item label="飞书推送">
          <el-switch v-model="feishuEnabled" active-text="启用" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="飞书 Webhook" v-show="feishuEnabled">
          <el-input
            v-model="form.push_feishu_webhook"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
            style="max-width: 520px"
          />
        </el-form-item>
        <el-form-item label="微信公众号推送">
          <el-switch v-model="wechatEnabled" active-text="启用" inactive-text="关闭" />
          <el-tag v-if="wechatEnabled" size="small" type="info" style="margin-left: 12px">即将支持</el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 输出设置 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header">
          <span>📁 输出设置</span>
          <el-tag size="small" type="danger" effect="plain">output</el-tag>
        </div>
      </template>
      <el-form label-width="160px" label-position="right">
        <el-form-item label="存档目录">
          <el-input v-model="form.output_archive_dir" style="max-width: 320px" />
        </el-form-item>
        <el-form-item label="文件名格式">
          <el-input v-model="form.output_filename_format" style="max-width: 400px" />
          <div class="form-hint">支持 {timestamp} 占位符</div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 定时任务设置 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header">
          <span>⏰ 定时任务设置</span>
          <el-tag size="small" :type="scheduleEnabled ? 'success' : 'info'" effect="plain">
            {{ scheduleEnabled ? '运行中' : '已关闭' }}
          </el-tag>
        </div>
      </template>
      <el-form label-width="160px" label-position="right">
        <el-form-item label="启用定时采集">
          <el-switch v-model="scheduleEnabled" active-text="启用" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="执行时间" v-show="scheduleEnabled">
          <el-input
            v-model="form.schedule_time"
            placeholder="08:00"
            style="max-width: 320px"
          />
          <div class="form-hint">24小时制，多个时间点用逗号分隔，如 08:00,18:00</div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 保存按钮 -->
    <div class="save-bar">
      <el-button type="primary" size="large" :loading="saving" @click="handleSave">
        💾 保存所有配置
      </el-button>
      <el-button size="large" @click="loadSettings">重新加载</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSettings, updateSettings } from '@/api/settings'

const loading = ref(false)
const saving = ref(false)

// 表单数据（key-value 字符串对照）
const form = ref<Record<string, string>>({
  ai_api_key: '',
  ai_base_url: '',
  ai_model_name: '',
  ai_temperature: '0.7',
  ai_system_prompt: '',
  fetch_hours_ago: '48',
  fetch_max_summary_length: '500',
  fetch_max_news_for_ai: '15',
  fetch_timeout: '10',
  push_feishu_enabled: 'True',
  push_feishu_webhook: '',
  push_wechat_enabled: 'False',
  output_archive_dir: 'archive',
  output_filename_format: 'AINews_{timestamp}.md',
  schedule_enabled: 'False',
  schedule_time: '08:00',
})

// 数值型的 computed 双向绑定
const temperatureValue = computed({
  get: () => Math.round(parseFloat(form.value.ai_temperature || '0.7') * 100),
  set: (v: number) => { form.value.ai_temperature = (v / 100).toFixed(2) },
})
const fetchHoursAgo = computed({
  get: () => parseInt(form.value.fetch_hours_ago) || 48,
  set: (v: number) => { form.value.fetch_hours_ago = String(v) },
})
const fetchMaxSummary = computed({
  get: () => parseInt(form.value.fetch_max_summary_length) || 500,
  set: (v: number) => { form.value.fetch_max_summary_length = String(v) },
})
const fetchMaxNews = computed({
  get: () => parseInt(form.value.fetch_max_news_for_ai) || 15,
  set: (v: number) => { form.value.fetch_max_news_for_ai = String(v) },
})
const fetchTimeout = computed({
  get: () => parseInt(form.value.fetch_timeout) || 10,
  set: (v: number) => { form.value.fetch_timeout = String(v) },
})
const feishuEnabled = computed({
  get: () => form.value.push_feishu_enabled === 'True',
  set: (v: boolean) => { form.value.push_feishu_enabled = v ? 'True' : 'False' },
})
const wechatEnabled = computed({
  get: () => form.value.push_wechat_enabled === 'True',
  set: (v: boolean) => { form.value.push_wechat_enabled = v ? 'True' : 'False' },
})
const scheduleEnabled = computed({
  get: () => form.value.schedule_enabled === 'True',
  set: (v: boolean) => { form.value.schedule_enabled = v ? 'True' : 'False' },
})

async function loadSettings() {
  loading.value = true
  try {
    const data = await fetchSettings()
    // 将分组数据 flatten 到 form
    for (const category of Object.values(data)) {
      for (const [key, item] of Object.entries(category)) {
        if (key in form.value) {
          form.value[key] = item.value
        }
      }
    }
  } catch { /* handled by interceptor */ }
  finally { loading.value = false }
}

async function handleSave() {
  saving.value = true
  try {
    await updateSettings({ ...form.value })
    ElMessage.success('🎉 配置保存成功！下次采集任务将使用新配置。')
  } catch { /* handled by interceptor */ }
  finally { saving.value = false }
}

onMounted(() => loadSettings())
</script>

<style scoped>
.settings-page {
  max-width: 860px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-card :deep(.el-card__header) {
  padding: 14px 20px;
  background-color: #fafafa;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 15px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.temp-tag {
  font-size: 16px;
  font-weight: 600;
  min-width: 56px;
  text-align: center;
}

.save-bar {
  display: flex;
  gap: 12px;
  padding: 20px 0;
  position: sticky;
  bottom: 0;
  background: #f5f7fa;
}
</style>
