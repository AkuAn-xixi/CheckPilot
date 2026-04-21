<template>
  <div class="min-h-screen flex flex-col">
    <!-- 顶部导航栏 -->
    <header class="bg-primary text-white shadow">
      <div class="container mx-auto px-4 py-3 flex justify-between items-center">
        <h1 class="text-xl font-bold">ADB 控制工具</h1>
        <div v-if="currentDevice" class="text-sm bg-blue-700 px-3 py-1 rounded-full">
          当前设备: {{ currentDevice }}
        </div>
      </div>
    </header>

    <!-- 主要内容区 -->
    <main class="flex-grow container mx-auto px-4 py-6">
      <div class="flex flex-col md:flex-row gap-6">
        <!-- 左侧导航 -->
        <div class="w-full md:w-64">
          <div class="card">
            <h2 class="mb-4">功能菜单</h2>
            <nav>
              <router-link to="/" class="nav-link" active-class="active">
                首页
              </router-link>
              <router-link to="/devices" class="nav-link" active-class="active">
                设备管理
              </router-link>
              <router-link to="/commands" class="nav-link" active-class="active">
                命令执行
              </router-link>
              <router-link to="/excel" class="nav-link" active-class="active">
                Excel执行
              </router-link>
              <router-link to="/keymonitor" class="nav-link" active-class="active">
                按键监听
              </router-link>
            </nav>
          </div>
        </div>

        <!-- 右侧内容 -->
        <div class="flex-grow">
          <router-view />
        </div>
      </div>
    </main>

    <!-- 底部状态栏 -->
    <footer class="bg-gray-800 text-white py-3">
      <div class="container mx-auto px-4 text-sm">
        <div class="flex justify-between">
          <div>ADB Control Tool v1.1.0</div>
          <div>{{ statusMessage }}</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// 状态管理
const currentDevice = ref('')
const statusMessage = ref('就绪')

// 加载当前设备
onMounted(async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    if (data.device) {
      currentDevice.value = data.device
    }
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
})
</script>

<style scoped>
</style>
