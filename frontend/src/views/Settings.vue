<template>
  <div class="card">
    <h2 class="mb-4">设置</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- 执行设置 -->
      <div class="border rounded-lg p-4">
        <h3 class="font-medium mb-4">执行设置</h3>
        
        <div class="form-group">
          <label class="form-label">执行模式</label>
          <div class="space-y-2">
            <div class="flex items-center">
              <input 
                type="radio" 
                id="executionModeDirect" 
                v-model="settings.executionMode" 
                value="direct"
                class="mr-2"
              >
              <label for="executionModeDirect">直接执行</label>
            </div>
            <div class="flex items-center">
              <input 
                type="radio" 
                id="executionModeStep" 
                v-model="settings.executionMode" 
                value="step"
                class="mr-2"
              >
              <label for="executionModeStep">步进执行</label>
            </div>
          </div>
        </div>
        
        <div class="form-group mt-4">
          <label class="form-label">时间控制模式</label>
          <div class="space-y-2">
            <div class="flex items-center">
              <input 
                type="radio" 
                id="timeModeScript" 
                v-model="settings.timeControlMode" 
                value="script"
                class="mr-2"
              >
              <label for="timeModeScript">脚本时间</label>
            </div>
            <div class="flex items-center">
              <input 
                type="radio" 
                id="timeModeGlobal" 
                v-model="settings.timeControlMode" 
                value="global"
                class="mr-2"
              >
              <label for="timeModeGlobal">全局时间</label>
            </div>
          </div>
        </div>
        
        <div class="form-group mt-4" v-if="settings.timeControlMode === 'global'">
          <label class="form-label" for="globalDelay">全局延迟时间 (秒)</label>
          <input 
            type="number" 
            id="globalDelay" 
            v-model.number="settings.globalDelay" 
            class="form-input"
            min="0"
            step="0.1"
            placeholder="输入全局延迟时间"
          >
        </div>
      </div>
      
      <!-- 关于 -->
      <div class="border rounded-lg p-4">
        <h3 class="font-medium mb-4">关于</h3>
        
        <div class="space-y-3">
          <div>
            <p class="font-medium">应用名称</p>
            <p class="text-gray-600">ADB 控制工具</p>
          </div>
          <div>
            <p class="font-medium">版本</p>
            <p class="text-gray-600">1.0.0</p>
          </div>
          <div>
            <p class="font-medium">描述</p>
            <p class="text-gray-600">基于Web的ADB设备控制和命令执行工具</p>
          </div>
          <div>
            <p class="font-medium">功能</p>
            <ul class="list-disc pl-5 space-y-1 text-gray-600">
              <li>设备管理和选择</li>
              <li>命令序列执行</li>
              <li>Excel文件命令执行</li>
              <li>执行模式配置</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
    
    <div class="mt-6 flex justify-end">
      <button @click="saveSettings" class="btn btn-primary">
        保存设置
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// 状态管理
const settings = ref({
  executionMode: 'direct',
  timeControlMode: 'script',
  globalDelay: 1.0
})

// 加载设置
onMounted(() => {
  loadSettings()
})

// 加载设置
const loadSettings = () => {
  // 从localStorage加载设置
  const savedSettings = localStorage.getItem('adbControlSettings')
  if (savedSettings) {
    try {
      settings.value = JSON.parse(savedSettings)
    } catch (error) {
      console.error('加载设置失败:', error)
    }
  }
}

// 保存设置
const saveSettings = () => {
  // 保存到localStorage
  localStorage.setItem('adbControlSettings', JSON.stringify(settings.value))
  alert('设置已保存')
}
</script>
