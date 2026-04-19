import subprocess
import time
import pandas as pd


class ADBController:
    def __init__(self):
        self.last_settings = None  # 初始化为None，表示没有上次设置
        self.first_run = True  # 标记是否是第一次运行
        self.device_serial = None  # 存储当前连接的设备序列号

    def send_keyevent(self, keycode, keyname, delay=0):
        """发送ADB keyevent并可选延迟"""
        if not 1 <= keycode <= 999:
            raise ValueError("Keycode must be between 1 and 999")

        # 添加设备序列号参数
        device_arg = f"-s {self.device_serial} " if self.device_serial else ""
        command = f"adb {device_arg}shell input keyevent {keycode}"

        try:
            subprocess.run(command, shell=True, check=True)
            print(f"已发送: {keyname}")
            if delay > 0:
                time.sleep(delay)
        except subprocess.CalledProcessError as e:
            print(f"发送 {keyname} ({keycode}) 失败: {e}")

    def parse_single_command(self, cmd):
        """解析单个命令，格式如 HOME/1/1"""
        parts = cmd.split('/')
        if len(parts) != 3:
            raise ValueError(f"指令格式错误: '{cmd}'. 正确格式: 键名/次数/延迟时间")

        keyname, repeat, delay = parts
        return keyname.upper(), int(repeat), float(delay)

    # Keycode 映射表
    KEYCODE_MAP = {
        "OK": 23,  # ENTER 键
        "HOME": 3,
        "BACK": 4,
        "UP": 19,  # KEYCODE_DPAD_UP
        "DOWN": 20,  # KEYCODE_DPAD_DOWN
        "LEFT": 21,  # KEYCODE_DPAD_LEFT
        "RIGHT": 22,  # KEYCODE_DPAD_RIGHT
        "MENU": 82,
        "SETTING": 176,
        "DIGITAL0": 7,
        "DIGITAL1": 8,
        "DIGITAL2": 9,
        "DIGITAL3": 10,
        "DIGITAL4": 11,
        "DIGITAL5": 12,
        "DIGITAL6": 13,
        "DIGITAL7": 14,
        "DIGITAL8": 15,
        "DIGITAL9": 16,
        "APPS": 360,
        "POWER": 26,
        "SOURCE": 178,
        "CHUP": 82,
        "CHDOWN": 166,
        "EXIT": 167,
        "LIBRARY": 358,
        "VOLUMEUP": 24,
        "VOLUMEDOWN": 25,
        "NETFLIX": 132,
        "YOUTUBE": 131,
        "PRIME_VII": 134,
        "ACTIONS": 222,
        "FILES": 359,
        "MUTE": 164
    }

    def execute_commands(self, command_sequence, settings):
        """执行多条ADB命令"""
        commands = command_sequence.split(',')
        for cmd in commands:
            try:
                keyname, repeat, original_delay = self.parse_single_command(cmd.strip())
                if keyname not in self.KEYCODE_MAP:
                    print(f"错误: 未知按键 '{keyname}'. 可用按键: {list(self.KEYCODE_MAP.keys())}")
                    continue

                keycode = self.KEYCODE_MAP[keyname]
                for _ in range(repeat):
                    # 时间控制选择
                    if settings['time_control_mode'] == 'G':  # 全局时间模式
                        delay = settings['global_delay']
                    elif settings['time_control_mode'] == 'C':  # 自定义时间
                        delay_input = input(f"请输入 {keyname} 的等待时间(秒，默认 {original_delay}): ")
                        delay = float(delay_input) if delay_input else original_delay
                    else:  # 使用脚本时间
                        delay = original_delay

                    self.send_keyevent(keycode, keyname, delay)

                    # 执行模式控制
                    if settings['execution_mode'] == 'S':  # 步进模式
                        input("按回车继续...")

            except ValueError as e:
                print(f"指令 '{cmd}' 错误: {e}")

    def get_user_settings(self):
        """获取用户设置"""
        if self.first_run or self.last_settings is None:
            # 第一次运行或没有上次设置时，直接获取新设置
            self.first_run = False
            choice = 'N'
        else:
            choice = input("使用上次的设置? [Y]es/[N]o (默认 Y): ").strip().upper() or 'Y'

        if choice == 'Y':
            return self.last_settings.copy()

        # 选择执行模式
        execution_mode = input("执行模式? [D]irect直接执行/[S]tep-by-step步进执行 (默认 D): ").strip().upper() or 'D'
        while execution_mode not in ('D', 'S'):
            execution_mode = input("请输入 D 或 S: ").strip().upper()

        # 选择时间控制模式
        time_control_mode = input(
            "时间控制? [S]cript脚本时间/[C]ustom自定义/[G]lobal全局时间 (默认 S): ").strip().upper() or 'S'
        while time_control_mode not in ('S', 'C', 'G'):
            time_control_mode = input("请输入 S, C 或 G: ").strip().upper()

        global_delay = None
        if time_control_mode == 'G':
            global_delay = float(input("请输入全局延迟时间(秒): "))

        settings = {
            'execution_mode': execution_mode,
            'time_control_mode': time_control_mode,
            'global_delay': global_delay
        }
        self.last_settings = settings.copy()
        return settings

    def list_devices(self):
        """列出所有连接的ADB设备"""
        try:
            result = subprocess.run("adb devices", shell=True, check=True, capture_output=True, text=True)
            lines = result.stdout.splitlines()
            devices = []

            print("\n已连接的ADB设备:")
            for line in lines[1:]:  # 跳过第一行标题
                if line.strip() and "device" in line:
                    serial = line.split('\t')[0]
                    devices.append(serial)
                    print(f"- {serial}")

            return devices
        except subprocess.CalledProcessError as e:
            print(f"获取设备列表失败: {e}")
            return []

    def select_device(self):
        """选择要连接的ADB设备"""
        devices = self.list_devices()
        if not devices:
            print("没有找到连接的ADB设备")
            return False

        if len(devices) == 1:
            self.device_serial = devices[0]
            print(f"自动选择唯一设备: {self.device_serial}")
            return True

        while True:
            print("\n请选择要连接的设备:")
            for i, device in enumerate(devices):
                print(f"{i+1}. {device}")
            
            choice = input("请输入设备序号(1-{}): ".format(len(devices))).strip()
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(devices):
                    self.device_serial = devices[index]
                    print(f"已选择设备: {self.device_serial}")
                    return True
                else:
                    print(f"无效的设备序号，请输入 1-{len(devices)} 之间的数字")
            except ValueError:
                print("无效的输入，请输入数字")

    def read_excel_commands(self, excel_path, target_row=None):
        """读取Excel文件中的命令"""
        try:
            # 读取Excel文件
            df = pd.read_excel(excel_path)
            
            # 构建命令序列
            commands = []
            
            # 检查是否是SmartTV模板格式
            if 'preScript' in df.columns:
                print("检测到SmartTV模板格式，正在解析preScript列...")
                
                # 收集所有有效行的信息
                valid_rows = []
                skipped_rows = []
                
                for index, row in df.iterrows():
                    # 检查runOption列
                    if 'runOption' in df.columns:
                        run_option = str(row['runOption']).upper()
                        if run_option != 'Y':
                            skipped_rows.append((index, f"runOption不是Y (值为: {run_option})"))
                            continue
                    
                    # 检查oriStep和preScript列
                    ori_step = str(row.get('oriStep', '')).strip()
                    pre_script = str(row.get('preScript', '')).strip()
                    
                    if not ori_step and not pre_script:
                        skipped_rows.append((index, "oriStep和preScript列都为空，用例未识别"))
                        continue
                    
                    # 检查oriStep和preScript列中的命令格式
                    has_valid_command = False
                    
                    # 合并oriStep和preScript中的命令
                    combined_commands = []
                    
                    # 解析oriStep列中的命令
                    if ori_step:
                        ori_commands = ori_step.split(',')
                        for cmd in ori_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)
                    
                    # 解析preScript列中的命令
                    if pre_script:
                        pre_commands = pre_script.split(',')
                        for cmd in pre_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)
                    
                    # 检查合并后的命令
                    for cmd in combined_commands:
                        try:
                            parts = cmd.split('/')
                            if len(parts) == 3:
                                keyname = parts[0].upper()
                                repeat = int(parts[1])
                                delay = float(parts[2])
                                
                                # 验证按键名称
                                if keyname in self.KEYCODE_MAP:
                                    has_valid_command = True
                        except ValueError:
                            pass
                    
                    if has_valid_command:
                        valid_rows.append((index, row))
                    else:
                        skipped_rows.append((index, "oriStep和preScript列中没有有效命令"))
                
                # 打印有效行信息
                print(f"\n找到 {len(valid_rows)} 行有效命令:")
                for i, (index, row) in enumerate(valid_rows):
                    ori_step = str(row.get('oriStep', '')).strip()
                    pre_script = str(row.get('preScript', '')).strip()
                    
                    if ori_step and pre_script:
                        print(f"{i+1}. 第{index+2}行: oriStep=[{ori_step}], preScript=[{pre_script}]")
                    elif ori_step:
                        print(f"{i+1}. 第{index+2}行: oriStep=[{ori_step}]")
                    else:
                        print(f"{i+1}. 第{index+2}行: preScript=[{pre_script}]")
                
                # 打印被跳过的行信息
                if skipped_rows:
                    print(f"\n跳过了 {len(skipped_rows)} 行，原因如下:")
                    for index, reason in skipped_rows:
                        print(f"- 第{index+2}行: {reason}")
                
                # 如果指定了目标行
                if target_row is not None:
                    if 1 <= target_row <= len(valid_rows):
                        index, row = valid_rows[target_row-1]
                        print(f"\n执行第 {target_row} 行命令")
                        
                        # 合并oriStep和preScript中的命令
                        combined_commands = []
                        
                        # 解析oriStep列中的命令
                        ori_step = str(row.get('oriStep', '')).strip()
                        if ori_step:
                            ori_commands = ori_step.split(',')
                            for cmd in ori_commands:
                                cmd = cmd.strip()
                                if not cmd:
                                    continue
                                combined_commands.append(cmd)
                        
                        # 解析preScript列中的命令
                        pre_script = str(row.get('preScript', '')).strip()
                        if pre_script:
                            pre_commands = pre_script.split(',')
                            for cmd in pre_commands:
                                cmd = cmd.strip()
                                if not cmd:
                                    continue
                                combined_commands.append(cmd)
                        
                        # 执行合并后的命令
                        for cmd in combined_commands:
                            try:
                                parts = cmd.split('/')
                                if len(parts) == 3:
                                    keyname = parts[0].upper()
                                    repeat = int(parts[1])
                                    delay = float(parts[2])
                                    
                                    # 验证按键名称
                                    if keyname not in self.KEYCODE_MAP:
                                        print(f"警告: 第{index+2}行的按键 '{keyname}' 不存在，将被跳过")
                                        continue
                                    
                                    commands.append(f"{keyname}/{repeat}/{delay}")
                            except ValueError as e:
                                print(f"警告: 第{index+2}行的命令 '{cmd}' 格式错误，将被跳过: {e}")
                    else:
                        print(f"错误: 行号 {target_row} 超出范围 (1-{len(valid_rows)})")
                        return ""
            else:
                # 原始格式
                required_columns = ['keyname', 'repeat', 'delay']
                for col in required_columns:
                    if col not in df.columns:
                        raise ValueError(f"Excel文件缺少必要的列: {col}")
                
                # 收集所有有效行的信息
                valid_rows = []
                skipped_rows = []
                
                for index, row in df.iterrows():
                    try:
                        # 检查keyname列
                        keyname = str(row.get('keyname', '')).upper()
                        if not keyname:
                            skipped_rows.append((index, "keyname列为空"))
                            continue
                        
                        # 检查repeat列
                        repeat = int(row.get('repeat', 0))
                        if repeat <= 0:
                            skipped_rows.append((index, "repeat值必须大于0"))
                            continue
                        
                        # 检查delay列
                        delay = float(row.get('delay', 0))
                        if delay < 0:
                            skipped_rows.append((index, "delay值不能小于0"))
                            continue
                        
                        # 验证按键名称
                        if keyname not in self.KEYCODE_MAP:
                            skipped_rows.append((index, f"keyname '{keyname}' 不存在于按键映射表中"))
                            continue
                        
                        valid_rows.append((index, row))
                    except (ValueError, TypeError) as e:
                        skipped_rows.append((index, f"数据类型错误: {str(e)}"))
                
                # 打印有效行信息
                print(f"\n找到 {len(valid_rows)} 行有效命令:")
                for i, (index, row) in enumerate(valid_rows):
                    keyname = str(row['keyname']).upper()
                    repeat = int(row['repeat'])
                    delay = float(row['delay'])
                    print(f"{i+1}. 第{index+2}行: {keyname}/{repeat}/{delay}")
                
                # 打印被跳过的行信息
                if skipped_rows:
                    print(f"\n跳过了 {len(skipped_rows)} 行，原因如下:")
                    for index, reason in skipped_rows:
                        print(f"- 第{index+2}行: {reason}")
                
                # 如果指定了目标行
                if target_row is not None:
                    if 1 <= target_row <= len(valid_rows):
                        index, row = valid_rows[target_row-1]
                        print(f"\n执行第 {target_row} 行命令")
                        
                        keyname = str(row['keyname']).upper()
                        repeat = int(row['repeat'])
                        delay = float(row['delay'])
                        
                        # 验证按键名称
                        if keyname not in self.KEYCODE_MAP:
                            print(f"警告: 第{index+2}行的按键 '{keyname}' 不存在，将被跳过")
                        else:
                            commands.append(f"{keyname}/{repeat}/{delay}")
                    else:
                        print(f"错误: 行号 {target_row} 超出范围 (1-{len(valid_rows)})")
                        return ""
            
            return ",".join(commands)
        except Exception as e:
            print(f"读取Excel文件失败: {e}")
            return ""

    def main(self):
        print("ADB 按键控制工具 (支持多指令)")
        print("可用按键:", ", ".join(self.KEYCODE_MAP.keys()))

        # 设备选择
        if not self.select_device():
            print("无法继续，因为没有可用的ADB设备")
            return

        while True:
            try:
                # 模式选择
                print("\n请选择操作模式:")
                print("1. 输入命令直接执行")
                print("2. 输入Excel文件路径执行")
                print("3. 重新选择设备")
                print("4. 退出程序")
                
                mode = input("请输入模式编号(1-4): ").strip()
                
                if mode == "1":
                    # 模式1: 输入命令直接执行
                    print("\n模式1: 输入命令直接执行")
                    print("用法: 指令1,指令2,... (例如: OK/1/1,DOWN/1/1)")
                    user_input = input("请输入命令序列: ").strip()
                    if not user_input:
                        print("命令不能为空")
                        continue
                    
                    settings = self.get_user_settings()
                    self.execute_commands(user_input, settings)
                
                elif mode == "2":
                    # 模式2: 输入Excel文件路径执行
                    print("\n模式2: 输入Excel文件路径执行")
                    
                    # 列出当前目录下的Excel文件
                    import os
                    excel_files = []
                    current_dir = os.getcwd()
                    
                    print("\n当前目录下的Excel文件:")
                    for file in os.listdir(current_dir):
                        if file.endswith('.xlsx') or file.endswith('.xls'):
                            excel_files.append(file)
                            print(f"{len(excel_files)}. {file}")
                    
                    # 让用户选择Excel文件
                    if excel_files:
                        choice = input("\n请输入要选择的Excel文件序号(1-{}): ".format(len(excel_files))).strip()
                        try:
                            index = int(choice) - 1
                            if 0 <= index < len(excel_files):
                                excel_path = excel_files[index]
                                print(f"已选择文件: {excel_path}")
                            else:
                                print(f"无效的文件序号，请输入 1-{len(excel_files)} 之间的数字")
                                continue
                        except ValueError:
                            print("无效的输入，请输入数字")
                            continue
                    else:
                        print("当前目录下没有找到Excel文件")
                        # 让用户手动输入文件路径
                        excel_path = input("请输入Excel文件路径: ").strip()
                        if not excel_path:
                            print("文件路径不能为空")
                            continue
                    
                    # 读取Excel文件，显示有效行信息
                    print("\n正在读取Excel文件并分析有效命令...")
                    # 先调用一次read_excel_commands获取有效行信息
                    temp_commands = self.read_excel_commands(excel_path, None)
                    
                    # 让用户选择要执行的行号
                    target_row = input("\n请输入要执行的行号: ").strip()
                    try:
                        target_row = int(target_row)
                        if target_row < 1:
                            print("行号必须大于0")
                            continue
                    except ValueError:
                        print("无效的行号，请输入数字")
                        continue
                    
                    # 读取并执行指定行的命令
                    commands = self.read_excel_commands(excel_path, target_row)
                    if not commands:
                        print("没有可用的命令")
                        continue
                    
                    print(f"\n从Excel文件中读取到的命令: {commands}")
                    settings = self.get_user_settings()
                    self.execute_commands(commands, settings)
                
                elif mode == "3":
                    # 模式3: 重新选择设备
                    print("\n模式3: 重新选择设备")
                    self.select_device()
                
                elif mode == "4":
                    # 模式4: 退出程序
                    print("退出程序...")
                    break
                
                else:
                    print("无效的模式编号，请重新输入")

            except KeyboardInterrupt:
                print("\n退出程序...")
                break
            except ValueError as e:
                print(f"输入错误: {e}")


if __name__ == "__main__":
    controller = ADBController()
    controller.main()