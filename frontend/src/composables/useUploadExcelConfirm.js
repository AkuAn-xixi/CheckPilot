// 共用的"上传 Excel 前提示用户文件会生成副本"确认逻辑。
// 始终弹出确认弹窗，不提供"不再提示"跳过（用户要求每次上传都显示提示）。
import { ref } from 'vue'

export function useUploadExcelConfirm() {
  const visible = ref(false)
  // 用户点确认后要执行的实际"打开文件选择对话框"动作
  let pendingAction = null

  // 调用方传入"真正打开 file input 的函数"；点击上传时总是弹出确认弹窗，用户点确认才执行。
  const requestUpload = (action) => {
    if (typeof action !== 'function') return
    pendingAction = action
    visible.value = true
  }

  const confirmUpload = () => {
    visible.value = false
    const action = pendingAction
    pendingAction = null
    if (typeof action === 'function') action()
  }

  const cancelUpload = () => {
    visible.value = false
    pendingAction = null
  }

  return {
    uploadConfirmVisible: visible,
    requestUpload,
    confirmUpload,
    cancelUpload,
  }
}
