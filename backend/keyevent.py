import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import threading
import time
import math
import subprocess
import re

# 全局变量
window = None  # 主窗口引用
monitor_active = False  # 监控是否激活
monitor_stopping = False  # 监控是否正在停止
monitor_live_sequence = ''  # 实时监控序列
monitor_dataset_latest = ''  # 最新监控数据集
monitor_last_error = ''  # 最后错误信息
monitor_thread = None  # 监控线程
last_key = None  # 上一个按下的按键
last_key_time = 0  # 上一个按键按下的时间
monitor_start_time = 0  # 监控开始的时间

# 设备路径
# 注意：在不同的设备上，输入事件设备的路径可能不同
# 这里使用一个通用的命令，让ADB自动选择设备
# 如果需要指定具体设备，可以修改为"event4"、"event0"等
DEVICE = ""

# 按键名称客制化映射表
# 格式：{"原始按键名称": "客制化名称"}
KEY_CUSTOM_MAPPING = {
    "00fc": "SOURCE",
    "TAB":"BACK",
    "ENTER":"OK",
    "0233":"APPS",
    "0234":"LIBRARY",
    "0235":"FILES",
    "SETUP":"SRTTING",
    "CHANNELUP":"CHUP",
    "CHANNELDOWN":"CHDOWN",
    "1":"DIGITAL1",
    "2":"DIGITAL2",
    "3":"DIGITAL3",
    "4":"DIGITAL4",
    "5":"DIGITAL5",
    "6":"DIGITAL6",
    "7":"DIGITAL7",
    "8":"DIGITAL8",
    "9":"DIGITAL9",
    "0":"DIGITAL0",
    "F2":"NETFLIX",
    "F1":"YOUTUBE",
    "F4":"PRIME_VIDEO"

    # 可以在此添加更多映射
}

# 日志函数
def log(message):
    """打印日志"""
    print(f"[LOG] {message}")

# 启动监控线程
def start_key_monitor_th():
    """启动或停止按键监控线程"""
    global monitor_active, monitor_stopping, monitor_thread, monitor_live_sequence, monitor_dataset_latest, monitor_last_error
    
    if monitor_active:
        # 停止监控
        monitor_active = False
        monitor_stopping = True
        if monitor_thread:
            monitor_thread.join(timeout=2)
        monitor_stopping = False
        monitor_dataset_latest = monitor_live_sequence
        log("监控已停止")
    else:
        # 开始监控
        monitor_active = True
        monitor_stopping = False
        monitor_live_sequence = ''
        monitor_last_error = ''
        # 记录监控开始时间
        monitor_start_time = time.time()
        monitor_thread = threading.Thread(target=monitor_key_events, daemon=True)
        monitor_thread.start()
        log("监控已开始")

def monitor_key_events():
    """监控按键事件的线程函数"""
    global monitor_active, monitor_live_sequence, monitor_last_error, monitor_start_time
    
    # 根据DEVICE是否为空构建不同的ADB命令
    if DEVICE:
        cmd = f"adb shell getevent -lt /dev/input/{DEVICE}"
    else:
        # 不指定具体设备，获取所有输入事件
        cmd = "adb shell getevent -lt"
    
    # 打印ADB命令，用于调试
    log(f"执行命令：{cmd}")
    proc = None
    
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # 打印进程信息，用于调试
        log(f"进程已启动，PID: {proc.pid}")
        
        # 读取错误输出的线程
        def read_stderr():
            while monitor_active:
                error_line = proc.stderr.readline()
                if not error_line:
                    break
                log(f"ADB错误: {error_line.strip()}")
        
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        while monitor_active:
            line = proc.stdout.readline()
            if not line:
                break
            
            try:
                # 打印原始行内容，用于调试
                log(f"原始输出: {line.strip()}")
                
                # 检查是否包含EV_KEY
                if "EV_KEY" in line:
                    # 打印原始行内容，用于调试
                    log(f"EV_KEY行: {line.strip()}")
                    
                    # 使用更简单的方式解析ADB输出
                    # 分割行
                    parts = line.strip().split()
                    
                    # 打印分割结果，用于调试
                    log(f"分割结果: {parts}")
                    
                    # 确保我们有足够的部分
                    if len(parts) >= 5:
                        # 提取按键名称和状态
                        # 兼容不同的ADB输出格式
                        key_name = None
                        status = None
                        
                        # 尝试找到EV_KEY后面的两个部分
                        for i, part in enumerate(parts):
                            if part == "EV_KEY" and i + 2 < len(parts):
                                key_name = parts[i + 1]
                                status = parts[i + 2]
                                break
                        
                        # 如果找到按键名称和状态
                        if key_name and status:
                            # 打印提取的按键名称和状态
                            log(f"捕获到：按键={key_name}, 状态={status}")
                            
                            # 只在按键按下时记录，避免重复记录按下和释放事件
                            if status == 'DOWN':
                                # 去掉KEY_前缀，只保留按键名称
                                simplified_key = key_name.replace('KEY_', '')
                                # 应用客制化映射
                                custom_key = KEY_CUSTOM_MAPPING.get(simplified_key, simplified_key)
                                
                                # 全局变量
                                global last_key, last_key_time
                                
                                # 获取当前时间
                                current_time = time.time()
                                
                                # 每次按下按键都重置监控开始时间，使时钟重新开始计时
                                monitor_start_time = current_time
                                
                                # 检查是否是连续按下的同一个按键
                                if custom_key == last_key:
                                    # 计算时间差并向上取整（这是按下上一个按键后等待的时间）
                                    time_diff = math.ceil(current_time - last_key_time)
                                    # 检查序列中最后一行是否是当前按键的记录
                                    if monitor_live_sequence:
                                        lines = monitor_live_sequence.strip().split('\n')
                                        if lines:
                                            last_line = lines[-1]
                                            # 检查最后一行是否是当前按键的记录
                                            if last_line.startswith(custom_key + '/'):
                                                # 解析最后一行的计数和时间
                                                parts = last_line.split('/')
                                                if len(parts) >= 3:
                                                    last_count = int(parts[1])
                                                    last_time_diff = int(parts[2])
                                                    # 如果时间差相同，增加计数
                                                    if time_diff == last_time_diff:
                                                        # 移除最后一行
                                                        monitor_live_sequence = '\n'.join(lines[:-1]) + '\n'
                                                        # 添加更新后的记录
                                                        monitor_live_sequence += f"{custom_key}/{last_count + 1}/{time_diff}\n"
                                                    else:
                                                        # 时间差不同，添加新记录
                                                        monitor_live_sequence += f"{custom_key}/1/{time_diff}\n"
                                            else:
                                                # 最后一行不是当前按键的记录，添加新记录
                                                monitor_live_sequence += f"{custom_key}/1/{time_diff}\n"
                                    else:
                                        # 序列为空，添加新记录
                                        monitor_live_sequence += f"{custom_key}/1/{time_diff}\n"
                                    # 更新最后按键时间
                                    last_key_time = current_time
                                else:
                                    # 重置计数
                                    last_key = custom_key
                                    # 记录当前时间
                                    last_key_time = current_time
                                    # 添加新按键记录，包含次数和时间（首次按下时间为0）
                                    monitor_live_sequence += f"{custom_key}/1/0\n"
                                
                                # 限制序列长度，避免内存占用过大
                                if len(monitor_live_sequence) > 1000:
                                    monitor_live_sequence = monitor_live_sequence[-1000:]
                                
                                # 打印简化后的按键名称
                                log(f"简化后：{simplified_key}")
                                # 打印客制化后的按键名称
                                log(f"客制化后：{custom_key}")
                                # 打印当前序列
                                log(f"当前序列：{monitor_live_sequence}")
                        else:
                            log("无法提取按键名称和状态")                   
            except Exception as e:
                log(f"处理行时出错：{str(e)}")
                    
    except Exception as e:
        monitor_last_error = f"监控错误：{str(e)}"
        log(f"监控错误：{str(e)}")
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1)
                log(f"进程已终止")
            except Exception as e:
                log(f"终止进程时出错：{str(e)}")
                pass
        monitor_active = False
        log(f"监控已停止")

def open_key_monitor_ui():
    """打开按键监控UI窗口"""
    global window
    
    # 如果主窗口不存在，创建一个
    if window is None:
        window = tk.Tk()
        window.title('按键监控')
        window.geometry('300x100')
        
        # 添加一个按钮用于打开监控窗口
        open_btn = ttk.Button(window, text='打开监控窗口', command=open_key_monitor_ui)
        open_btn.pack(pady=20)
    
    # 新开页面进行监听操作
    ui = tk.Toplevel(window)
    ui.title('遥控操作监控')
    ui.geometry('520x350')
    
    # 确保窗口关闭时的清理
    def on_close():
        global monitor_active
        if monitor_active:
            monitor_active = False
        ui.destroy()
    
    ui.protocol("WM_DELETE_WINDOW", on_close)

    # 创建一个框架用于放置按钮和时钟
    top_frame = ttk.Frame(ui)
    top_frame.pack(pady=6, fill=tk.X)
    
    # 左侧放置按钮
    btn_frame = ttk.Frame(top_frame)
    btn_frame.pack(side=tk.LEFT)
    
    # 右侧放置时钟
    clock_frame = ttk.Frame(top_frame)
    clock_frame.pack(side=tk.RIGHT, padx=10)
    clock_label = ttk.Label(clock_frame, text='时间：00:00:00')
    clock_label.pack()
    
    # 状态标签（只在本窗口显示提示，不写主窗口日志）
    status = ttk.Label(ui, text='状态：已停止')
    status.pack(pady=4)
    
    def _toggle():
        # 单按钮开关：正在监听则停止，否则开始
        was_active = monitor_active
        start_key_monitor_th()
        # 立即刷新按钮文案与颜色，并给出提示（参考实时打印日志）
        try:
            if was_active:
                toggle_btn.configure(text='开始监听')
                try:
                    status.configure(text='状态：已停止')
                except Exception:
                    pass
            else:
                toggle_btn.configure(text='结束监听')
                try:
                    status.configure(text='状态：正在监听…')
                except Exception:
                    pass
        except Exception:
            pass
    
    toggle_btn = ttk.Button(btn_frame, text='开始监听', command=_toggle)
    toggle_btn.pack(side=tk.LEFT, padx=5)
    
    def _copy():
        seq = monitor_live_sequence if monitor_active else monitor_dataset_latest
        try:
            # 将换行符替换为逗号，使复制的内容以逗号分隔
            seq_no_newline = (seq or '').replace('\n', ',').strip()
            window.clipboard_clear()
            window.clipboard_append(seq_no_newline)
            try:
                status.configure(text='状态：序列已复制到剪贴板')
            except Exception:
                pass
            pass
        except Exception as e:
            try:
                status.configure(text=f'状态：复制失败：{e}')
            except Exception:
                pass
            try:
                log(f'复制失败：{e}')
            except Exception:
                pass
            pass
    
    ttk.Button(btn_frame, text='复制序列', command=_copy).pack(side=tk.LEFT, padx=5)

    txt = scrolledtext.ScrolledText(ui, height=12)
    txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

    def _tick_update():
        try:
            txt.delete('1.0', tk.END)
            if monitor_active:
                txt.insert(tk.END, monitor_live_sequence or '正在监听，尚无数据...')
                # 更新时钟
                if monitor_start_time > 0:
                    elapsed = int(time.time() - monitor_start_time)
                    hours = elapsed // 3600
                    minutes = (elapsed % 3600) // 60
                    seconds = elapsed % 60
                    time_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
                    clock_label.configure(text=f'时间：{time_str}')
            elif monitor_stopping:
                # 停止收尾阶段显示最后预览，避免闪现“未监听到遥控”
                txt.insert(tk.END, monitor_live_sequence or '正在停止，等待结果…')
                status.configure(text='状态：正在停止…')
            else:
                txt.insert(tk.END, monitor_dataset_latest or '未监听到遥控')
                # 停止时重置时钟
                clock_label.configure(text='时间：00:00:00')
            # 在监控窗口显示错误提示，不写主界面日志
            if monitor_last_error:
                status.configure(text=f'状态：{monitor_last_error}')
            else:
                if not monitor_active and not monitor_stopping:
                    status.configure(text='状态：已停止')
            # 同步按钮文案与颜色
            try:
                if monitor_active:
                    toggle_btn.configure(text='结束监听')
                elif monitor_stopping:
                    toggle_btn.configure(text='结束监听')
                else:
                    toggle_btn.configure(text='开始监听')
            except Exception:
                pass
        except Exception:
            pass
        try:
            ui.after(400, _tick_update)
        except Exception:
            pass
    
    _tick_update()

# 主函数
if __name__ == "__main__":
    try:
        # 创建主窗口
        window = tk.Tk()
        window.title('按键监控工具')
        window.geometry('300x100')
        
        # 添加按钮
        ttk.Label(window, text='按键监控工具').pack(pady=10)
        open_btn = ttk.Button(window, text='打开监控窗口', command=open_key_monitor_ui)
        open_btn.pack(pady=5)
        
        # 运行主循环
        window.mainloop()
    except Exception as e:
        print(f"主函数错误：{str(e)}")
        import traceback
        traceback.print_exc()