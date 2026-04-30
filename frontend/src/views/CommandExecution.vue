<template>
  <div class="card command-page">
    <div class="command-page-header">
      <div>
        <h2 class="mb-2">命令执行</h2>
        <p class="command-page-subtitle">直接发送 ADB 指令序列，命令说明和示例固定放在右侧，减少整页纵向占用。</p>
      </div>
    </div>
    
    <div v-if="!selectedDevice" class="bg-yellow-50 p-4 rounded-lg mb-6">
      <p class="text-warning mb-2">请先在设备管理页面选择一个ADB设备</p>
      <router-link to="/devices" class="btn btn-primary">
        前往设备管理
      </router-link>
    </div>
    
    <div v-else class="command-layout">
      <section class="command-main">
        <div class="form-group mb-0">
          <label class="form-label" for="commandInput">命令序列</label>
          <textarea 
            id="commandInput" 
            v-model="commandInput" 
            class="form-input command-input" 
            rows="4"
            placeholder="输入命令序列，格式为：KEYNAME/REPEAT/DELAY,KEYNAME/REPEAT/DELAY\n例如：OK/1/1,DOWN/1/1,UP/2/0.5"
          ></textarea>
        </div>

        <div class="command-actions">
          <button 
            @click="executeCommands" 
            class="btn btn-primary"
            :disabled="!commandInput.trim() || executing"
          >
            {{ executing ? '执行中...' : '执行命令' }}
          </button>
          <button @click="clearInput" class="btn btn-secondary">
            清空
          </button>
        </div>

        <div v-if="executionResults.length > 0" class="command-results">
          <h3 class="font-medium mb-3">执行结果</h3>
          <div class="border rounded-lg p-4 max-h-60 overflow-y-auto bg-white/80">
            <div 
              v-for="(result, index) in executionResults" 
              :key="index"
              class="mb-2 pb-2 border-b last:border-b-0"
            >
              <div :class="result.status === 'success' ? 'status-success' : 'status-error'">
                {{ result.message }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside class="command-side">
        <div class="command-panel">
          <h3 class="font-medium mb-2">命令格式说明</h3>
          <p class="text-sm mb-2">
            每条命令由三部分组成，用斜杠分隔：
          </p>
          <ul class="list-disc pl-5 space-y-1 text-sm">
            <li><strong>KEYNAME</strong>：按键名称（如 OK, HOME, UP, DOWN 等）</li>
            <li><strong>REPEAT</strong>：执行次数（整数）</li>
            <li><strong>DELAY</strong>：延迟时间（秒，支持小数）</li>
          </ul>
          <p class="text-sm mt-2">
            多条命令之间用逗号分隔。
          </p>
        </div>

        <div class="command-panel command-panel-soft">
          <h3 class="font-medium mb-2">示例命令</h3>
          <div class="command-example-grid text-sm">
            <div class="bg-white p-2 rounded">
              <code>HOME/1/1,OK/1/1</code>
              <p class="text-gray-600">返回主屏幕，然后按OK键</p>
            </div>
            <div class="bg-white p-2 rounded">
              <code>UP/3/0.5,DOWN/3/0.5</code>
              <p class="text-gray-600">向上移动3次，每次延迟0.5秒，然后向下移动3次</p>
            </div>
            <div class="bg-white p-2 rounded">
              <code>LEFT/1/1,RIGHT/1/1,OK/1/1</code>
              <p class="text-gray-600">向左移动，向右移动，然后按OK键</p>
            </div>
            <div class="bg-white p-2 rounded">
              <code>BACK/2/1, HOME/1/1</code>
              <p class="text-gray-600">按BACK键2次，每次延迟1秒，然后返回主屏幕</p>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// 状态管理
const selectedDevice = ref('')
const commandInput = ref('')
const executionResults = ref([])
const executing = ref(false)
 

// 加载当前设备
onMounted(async () => {
  await loadCurrentDevice()
})

// 加载当前设备
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

 

// 执行命令
const executeCommands = async () => {
  if (!commandInput.value.trim()) {
    alert('请输入命令序列')
    return
  }
  
  executing.value = true
  executionResults.value = []
  
  try {
    const response = await fetch('/api/devices/commands/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ commands: commandInput.value })
    })
    
    if (!response.ok) {
      let errorMessage = '执行命令失败'
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorMessage
      } catch {
        // ignore json parse failure and keep fallback message
      }
      throw new Error(errorMessage)
    }
    
    const data = await response.json()
    executionResults.value = data.results
  } catch (error) {
    console.error('执行命令失败:', error)
    executionResults.value = [
      { status: 'error', message: '执行命令失败：' + error.message }
    ]
  } finally {
    executing.value = false
  }
}

// 清空输入
const clearInput = () => {
  commandInput.value = ''
  executionResults.value = []
}
</script>

<style scoped>
.command-page {
  padding: 22px;
}

.command-page-header {
  margin-bottom: 16px;
}

.command-page-subtitle {
  color: #6b7280;
  font-size: 0.95rem;
  line-height: 1.55;
}

.command-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  gap: 18px;
  align-items: start;
}

.command-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.command-input {
  min-height: 132px;
}

.command-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.command-results {
  margin-top: 2px;
}

.command-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.command-panel {
  padding: 16px;
  border-radius: 24px;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.command-panel-soft {
  background: rgba(239, 246, 255, 0.88);
}

.command-example-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

@media (max-width: 1200px) {
  .command-layout {
    grid-template-columns: 1fr;
  }
}
</style>
