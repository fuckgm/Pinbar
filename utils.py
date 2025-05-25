#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工具函数模块
包含信号处理、安全输入等通用功能
"""

import sys
import inquirer
from typing import Any, List, Optional, Union

def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print('\n👋 程序被用户中断')
    sys.exit(0)

def safe_list_input(message: str, choices: List[Union[str, tuple]]) -> Optional[Any]:
    """
    安全的列表输入，支持ESC返回
    
    Args:
        message: 提示消息
        choices: 选择列表，可以是字符串列表或(显示文本, 值)元组列表
    
    Returns:
        选择的值，如果用户取消则返回None
    """
    try:
        # 处理不同格式的choices
        if choices and isinstance(choices[0], tuple):
            # 格式: [(显示文本, 值), ...]
            display_choices = [choice[0] for choice in choices]
            values = [choice[1] for choice in choices]
        else:
            # 格式: [字符串, ...]
            display_choices = choices
            values = choices
        
        # 使用inquirer进行选择
        selected = inquirer.list_input(message, choices=display_choices)
        
        # 返回对应的值
        if selected in display_choices:
            index = display_choices.index(selected)
            return values[index]
        else:
            return selected
            
    except KeyboardInterrupt:
        print("\n🔙 返回上层菜单")
        return None
    except Exception as e:
        print(f"\n❌ 输入处理失败: {e}")
        return None

def safe_confirm(message: str, default: bool = True) -> Optional[bool]:
    """
    安全的确认输入，支持ESC返回
    
    Args:
        message: 提示消息
        default: 默认值
    
    Returns:
        用户选择的布尔值，如果用户取消则返回None
    """
    try:
        return inquirer.confirm(message, default=default)
    except KeyboardInterrupt:
        print("\n🔙 返回上层菜单")
        return None
    except Exception as e:
        print(f"\n❌ 确认输入失败: {e}")
        return default

def safe_text_input(message: str, default: str = "") -> Optional[str]:
    """
    安全的文本输入，支持ESC返回
    
    Args:
        message: 提示消息
        default: 默认值
    
    Returns:
        用户输入的文本，如果用户取消则返回None
    """
    try:
        result = inquirer.text(message, default=default)
        return result if result is not None else default
    except KeyboardInterrupt:
        print("\n🔙 返回上层菜单")
        return None
    except Exception as e:
        print(f"\n❌ 文本输入失败: {e}")
        return default

def safe_number_input(message: str, default: Union[int, float] = 0, 
                     input_type: type = float, min_value: Optional[Union[int, float]] = None,
                     max_value: Optional[Union[int, float]] = None) -> Optional[Union[int, float]]:
    """
    安全的数字输入，支持验证和ESC返回
    
    Args:
        message: 提示消息
        default: 默认值
        input_type: 输入类型 (int 或 float)
        min_value: 最小值
        max_value: 最大值
    
    Returns:
        用户输入的数字，如果用户取消则返回None
    """
    while True:
        try:
            # 构建提示消息
            prompt = message
            if min_value is not None or max_value is not None:
                range_info = []
                if min_value is not None:
                    range_info.append(f"≥{min_value}")
                if max_value is not None:
                    range_info.append(f"≤{max_value}")
                prompt += f" ({', '.join(range_info)})"
            
            text_input = safe_text_input(f"{prompt} (默认: {default})", default=str(default))
            
            if text_input is None:
                return None
            
            if not text_input.strip():
                return default
            
            # 转换为数字
            if input_type == int:
                value = int(float(text_input))  # 先转float再转int，支持"3.0"这样的输入
            else:
                value = float(text_input)
            
            # 验证范围
            if min_value is not None and value < min_value:
                print(f"❌ 输入值 {value} 小于最小值 {min_value}")
                continue
            
            if max_value is not None and value > max_value:
                print(f"❌ 输入值 {value} 大于最大值 {max_value}")
                continue
            
            return value
            
        except ValueError:
            print(f"❌ 请输入有效的{'整数' if input_type == int else '数字'}")
            continue
        except KeyboardInterrupt:
            print("\n🔙 返回上层菜单")
            return None
        except Exception as e:
            print(f"❌ 数字输入处理失败: {e}")
            return default

def safe_percentage_input(message: str, default: float = 0.0) -> Optional[float]:
    """
    安全的百分比输入 (0-100)
    
    Args:
        message: 提示消息
        default: 默认值 (0-100)
    
    Returns:
        用户输入的百分比值 (0-1)，如果用户取消则返回None
    """
    result = safe_number_input(f"{message} (%)", default=default * 100, 
                              input_type=float, min_value=0, max_value=100)
    
    if result is not None:
        return result / 100.0
    return None

def format_number(value: Union[int, float], decimals: int = 2, 
                 use_separator: bool = True) -> str:
    """
    格式化数字显示
    
    Args:
        value: 要格式化的数字
        decimals: 小数位数
        use_separator: 是否使用千位分隔符
    
    Returns:
        格式化后的字符串
    """
    try:
        if use_separator:
            return f"{value:,.{decimals}f}"
        else:
            return f"{value:.{decimals}f}"
    except:
        return str(value)

def format_percentage(value: float, decimals: int = 2) -> str:
    """
    格式化百分比显示
    
    Args:
        value: 百分比值 (0-1)
        decimals: 小数位数
    
    Returns:
        格式化后的百分比字符串
    """
    try:
        return f"{value * 100:.{decimals}f}%"
    except:
        return "0.00%"

def format_currency(value: Union[int, float], currency: str = "USDT", 
                   decimals: int = 2) -> str:
    """
    格式化货币显示
    
    Args:
        value: 金额
        currency: 货币单位
        decimals: 小数位数
    
    Returns:
        格式化后的货币字符串
    """
    try:
        formatted_value = format_number(value, decimals, use_separator=True)
        return f"{formatted_value} {currency}"
    except:
        return f"0.00 {currency}"

def print_separator(char: str = "=", length: int = 60, title: str = ""):
    """
    打印分隔线
    
    Args:
        char: 分隔符字符
        length: 分隔线长度
        title: 标题（可选）
    """
    if title:
        title_length = len(title)
        if title_length + 4 <= length:
            padding = (length - title_length - 2) // 2
            print(f"{char * padding} {title} {char * padding}")
        else:
            print(title)
            print(char * length)
    else:
        print(char * length)

def print_status(message: str, status: str = "info"):
    """
    打印带状态的消息
    
    Args:
        message: 消息内容
        status: 状态类型 (info, success, warning, error)
    """
    status_icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "loading": "⏳",
        "complete": "🎉"
    }
    
    icon = status_icons.get(status, "ℹ️")
    print(f"{icon} {message}")

def print_progress(current: int, total: int, description: str = ""):
    """
    打印进度信息
    
    Args:
        current: 当前进度
        total: 总数
        description: 描述信息
    """
    if total <= 0:
        return
    
    percentage = (current / total) * 100
    bar_length = 30
    filled_length = int(bar_length * current // total)
    
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    
    progress_text = f"[{current}/{total}] {bar} {percentage:.1f}%"
    if description:
        progress_text = f"{description}: {progress_text}"
    
    print(f"\r{progress_text}", end="", flush=True)
    
    if current >= total:
        print()  # 完成后换行

def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    截断字符串
    
    Args:
        text: 要截断的字符串
        max_length: 最大长度
        suffix: 截断后缀
    
    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def validate_file_path(file_path: str, extensions: Optional[List[str]] = None) -> bool:
    """
    验证文件路径
    
    Args:
        file_path: 文件路径
        extensions: 允许的文件扩展名列表
    
    Returns:
        是否有效
    """
    import os
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False
        
        # 检查是否是文件
        if not os.path.isfile(file_path):
            return False
        
        # 检查文件扩展名
        if extensions:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in [ext.lower() for ext in extensions]:
                return False
        
        return True
        
    except:
        return False

def create_directory(dir_path: str, exist_ok: bool = True) -> bool:
    """
    创建目录
    
    Args:
        dir_path: 目录路径
        exist_ok: 如果目录已存在是否报错
    
    Returns:
        是否成功创建
    """
    import os
    
    try:
        os.makedirs(dir_path, exist_ok=exist_ok)
        return True
    except Exception as e:
        print(f"❌ 创建目录失败: {e}")
        return False

def get_file_size(file_path: str) -> Optional[int]:
    """
    获取文件大小
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件大小（字节），失败返回None
    """
    import os
    
    try:
        return os.path.getsize(file_path)
    except:
        return None

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小显示
    
    Args:
        size_bytes: 文件大小（字节）
    
    Returns:
        格式化后的大小字符串
    """
    try:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    except:
        return "Unknown"

def get_timestamp_string(include_microseconds: bool = False) -> str:
    """
    获取当前时间戳字符串
    
    Args:
        include_microseconds: 是否包含微秒
    
    Returns:
        时间戳字符串
    """
    from datetime import datetime
    
    if include_microseconds:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    else:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

def retry_on_failure(func, max_retries: int = 3, delay: float = 1.0, 
                    exceptions: tuple = (Exception,)):
    """
    失败重试装饰器
    
    Args:
        func: 要重试的函数
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        exceptions: 需要重试的异常类型
    
    Returns:
        装饰器函数
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    print(f"⚠️ 第{attempt + 1}次尝试失败，{delay}秒后重试: {e}")
                    time.sleep(delay)
                else:
                    print(f"❌ 所有重试都失败了: {e}")
        
        raise last_exception
    
    return wrapper

def measure_execution_time(func):
    """
    测量函数执行时间的装饰器
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"⏱️ {func.__name__} 执行时间: {execution_time:.2f} 秒")
        
        return result
    
    return wrapper

def log_function_call(func):
    """
    记录函数调用的装饰器
    """
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"🔧 调用函数: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            print(f"✅ 函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            print(f"❌ 函数 {func.__name__} 执行失败: {e}")
            raise
    
    return wrapper

class ProgressBar:
    """简单的进度条类"""
    
    def __init__(self, total: int, description: str = "", width: int = 50):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
    
    def update(self, increment: int = 1):
        """更新进度"""
        self.current = min(self.current + increment, self.total)
        self._display()
    
    def set_progress(self, current: int):
        """设置当前进度"""
        self.current = min(max(current, 0), self.total)
        self._display()
    
    def _display(self):
        """显示进度条"""
        if self.total <= 0:
            return
        
        percentage = (self.current / self.total) * 100
        filled_width = int(self.width * self.current // self.total)
        
        bar = "█" * filled_width + "░" * (self.width - filled_width)
        
        progress_text = f"\r{self.description} [{bar}] {self.current}/{self.total} ({percentage:.1f}%)"
        print(progress_text, end="", flush=True)
        
        if self.current >= self.total:
            print()  # 完成后换行
    
    def finish(self):
        """完成进度条"""
        self.current = self.total
        self._display()

# 导出主要函数
__all__ = [
    'signal_handler',
    'safe_list_input', 
    'safe_confirm', 
    'safe_text_input', 
    'safe_number_input',
    'safe_percentage_input',
    'format_number', 
    'format_percentage', 
    'format_currency',
    'print_separator', 
    'print_status', 
    'print_progress',
    'truncate_string',
    'validate_file_path', 
    'create_directory',
    'get_file_size', 
    'format_file_size',
    'get_timestamp_string',
    'retry_on_failure', 
    'measure_execution_time', 
    'log_function_call',
    'ProgressBar'
]