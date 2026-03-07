<template>
  <div class="rss-management">
    <!-- 顶部操作栏 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索 RSS 源名称..."
            :prefix-icon="Search"
            clearable
            style="width: 260px"
            @input="handleSearch"
          />
          <el-select
            v-model="filterCategory"
            placeholder="全部分类"
            clearable
            style="width: 140px"
            @change="loadSources"
          >
            <el-option label="海外媒体" value="海外媒体" />
            <el-option label="国内媒体" value="国内媒体" />
          </el-select>
        </div>
        <el-button type="primary" :icon="Plus" @click="openDialog()">
          添加 RSS 源
        </el-button>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        :data="sourceList"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无 RSS 源，请点击上方按钮添加"
      >
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <span class="source-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="RSS 地址" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <a :href="row.url" target="_blank" class="source-url">{{ row.url }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.category === '海外媒体' ? 'primary' : 'success'" size="small" effect="plain">
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="handleToggleActive(row)"
              :loading="row._switching"
            />
          </template>
        </el-table-column>
        <el-table-column prop="retry_times" label="重试次数" width="90" align="center" />
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :icon="Edit" @click="openDialog(row)">
              编辑
            </el-button>
            <el-button link type="danger" size="small" :icon="Delete" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑 RSS 源' : '添加 RSS 源'"
      width="520px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="90px"
        @submit.prevent
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：TechCrunch AI专区" />
        </el-form-item>
        <el-form-item label="RSS 地址" prop="url">
          <el-input v-model="form.url" placeholder="https://example.com/feed" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" style="width: 100%">
            <el-option label="海外媒体" value="海外媒体" />
            <el-option label="国内媒体" value="国内媒体" />
            <el-option label="默认" value="默认" />
          </el-select>
        </el-form-item>
        <el-form-item label="重试次数" prop="retry_times">
          <el-input-number v-model="form.retry_times" :min="0" :max="10" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '确认添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  fetchRssSources,
  createRssSource,
  updateRssSource,
  deleteRssSource,
  type RssSource,
  type RssSourceForm,
} from '@/api/rss'

// ====== 列表相关 ======
const loading = ref(false)
const sourceList = ref<(RssSource & { _switching?: boolean })[]>([])
const searchKeyword = ref('')
const filterCategory = ref('')

async function loadSources() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterCategory.value) params.category = filterCategory.value
    sourceList.value = await fetchRssSources(params)
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadSources(), 300)
}

// ====== 启用/禁用切换 ======
async function handleToggleActive(row: RssSource & { _switching?: boolean }) {
  row._switching = true
  try {
    await updateRssSource(row.id, { is_active: row.is_active })
    ElMessage.success(`已${row.is_active ? '启用' : '禁用'} ${row.name}`)
  } catch {
    row.is_active = !row.is_active // 回滚
  } finally {
    row._switching = false
  }
}

// ====== 新增/编辑对话框 ======
const dialogVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const defaultForm: RssSourceForm = {
  name: '',
  url: '',
  is_active: true,
  category: '默认',
  retry_times: 3,
  fetch_interval: 60,
  description: '',
}

const form = reactive<RssSourceForm>({ ...defaultForm })

const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [
    { required: true, message: '请输入 RSS 地址', trigger: 'blur' },
    { type: 'url', message: '请输入有效的 URL 地址', trigger: 'blur' },
  ],
}

function openDialog(row?: RssSource) {
  if (row) {
    isEditing.value = true
    editingId.value = row.id
    Object.assign(form, {
      name: row.name,
      url: row.url,
      is_active: row.is_active,
      category: row.category,
      retry_times: row.retry_times,
      fetch_interval: row.fetch_interval,
      description: row.description,
    })
  } else {
    isEditing.value = false
    editingId.value = null
    Object.assign(form, defaultForm)
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()

  submitting.value = true
  try {
    if (isEditing.value && editingId.value) {
      await updateRssSource(editingId.value, { ...form })
      ElMessage.success('修改成功')
    } else {
      await createRssSource({ ...form })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadSources()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    submitting.value = false
  }
}

// ====== 删除 ======
async function handleDelete(row: RssSource) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${row.name}" 吗？此操作不可撤销。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await deleteRssSource(row.id)
    ElMessage.success('删除成功')
    loadSources()
  } catch {
    // 用户取消或删除失败
  }
}

// ====== 初始化 ======
onMounted(() => loadSources())
</script>

<style scoped>
.rss-management {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

.source-name {
  font-weight: 500;
  color: #303133;
}

.source-url {
  color: #409eff;
  text-decoration: none;
  font-size: 13px;
}

.source-url:hover {
  text-decoration: underline;
}
</style>
