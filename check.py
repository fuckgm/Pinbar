#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖安装脚本
自动检测Python版本并安装兼容的依赖包
"""

import sys
import subprocess
import importlib
import pkg_resources

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"🐍 当前Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3:
        print("❌ 错误: 需要Python 3.7或更高版本")
        return False
    
    if version.minor < 7:
        print("❌ 错误: 需要Python 3.7或更高版本")
        return False
    
    print("✅ Python版本检查通过")
    return True

def install_package(package_name, version_spec=""):
    """安装单个包"""
    try:
        full_name = f"{package_name}{version_spec}"
        print(f"📦 安装 {full_name}...")
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", full_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"✅ {package_name} 安装成功")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ {package_name} 安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def check_package_installed(package_name):
    """检查包是否已安装"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

def get_compatible_packages():
    """根据Python版本获取兼容的包列表"""
    version = sys.version_info
    
    # 基础依赖包
    packages = [
        ("backtrader", ""),
        ("pandas", ">=1.3.0" if version.minor >= 8 else ">=1.1.0"),
        ("numpy", ">=1.21.0" if version.minor >= 8 else ">=1.19.0"),
        ("python-binance", ""),
        ("plotly", ">=5.0.0"),
        ("jinja2", ">=3.0.0" if version.minor >= 8 else ">=2.11.0"),
        ("inquirer", ">=2.8.0"),
        ("scipy", ">=1.7.0" if version.minor >= 8 else ">=1.5.0"),
    ]
    
    # 可选依赖
    optional_packages = [
        ("openpyxl", ">=3.0.0"),  # Excel支持
        ("pyyaml", ""),           # YAML配置支持
    ]
    
    return packages, optional_packages

def install_dependencies():
    """安装所有依赖"""
    print("🚀 开始安装Pinbar策略依赖包...")
    print("=" * 50)
    
    # 检查Python版本
    if not check_python_version():
        return False
    
    # 升级pip
    print("\n📦 升级pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        print("✅ pip升级成功")
    except:
        print("⚠️ pip升级失败，继续安装...")
    
    # 获取兼容的包列表
    packages, optional_packages = get_compatible_packages()
    
    # 安装核心依赖
    print("\n📚 安装核心依赖...")
    failed_packages = []
    
    for package_name, version_spec in packages:
        if not install_package(package_name, version_spec):
            failed_packages.append(package_name)
    
    # 安装可选依赖
    print("\n📋 安装可选依赖...")
    optional_failed = []
    
    for package_name, version_spec in optional_packages:
        if not install_package(package_name, version_spec):
            optional_failed.append(package_name)
    
    # 验证安装
    print("\n🔍 验证安装结果...")
    
    core_modules = ["backtrader", "pandas", "numpy", "binance", "plotly", "jinja2", "inquirer", "scipy"]
    
    all_installed = True
    for module in core_modules:
        if check_package_installed(module):
            print(f"✅ {module} - 已安装")
        else:
            print(f"❌ {module} - 未安装")
            all_installed = False
    
    # 输出结果
    print("\n" + "=" * 50)
    if all_installed and not failed_packages:
        print("🎉 所有核心依赖安装成功!")
        print("\n🚀 现在可以运行策略:")
        print("   python main.py")
    else:
        print("⚠️ 部分依赖安装失败")
        if failed_packages:
            print(f"❌ 失败的核心包: {', '.join(failed_packages)}")
        if optional_failed:
            print(f"⚠️ 失败的可选包: {', '.join(optional_failed)}")
        print("\n🔧 手动安装失败的包:")
        for pkg in failed_packages:
            print(f"   pip install {pkg}")
    
    if optional_failed:
        print(f"\n💡 可选包安装失败，不影响核心功能:")
        for pkg in optional_failed:
            if pkg == "openpyxl":
                print(f"   - {pkg}: 影响Excel导出功能")
            elif pkg == "pyyaml":
                print(f"   - {pkg}: 影响YAML配置文件支持")
    
    return all_installed

def create_simple_requirements():
    """创建简化的requirements文件"""
    simple_reqs = """# 简化版依赖 - 手动安装用
backtrader
pandas
numpy
python-binance
plotly
jinja2
inquirer
scipy
"""
    
    with open("requirements_simple.txt", "w", encoding="utf-8") as f:
        f.write(simple_reqs)
    
    print("📄 已创建 requirements_simple.txt")
    print("   可以使用: pip install -r requirements_simple.txt")

if __name__ == "__main__":
    try:
        success = install_dependencies()
        
        if not success:
            print("\n🆘 如果自动安装失败，请尝试:")
            print("1. 手动安装: pip install backtrader pandas numpy python-binance plotly jinja2 inquirer scipy")
            print("2. 或使用简化版: pip install -r requirements_simple.txt")
            create_simple_requirements()
        
    except KeyboardInterrupt:
        print("\n❌ 安装被用户中断")
    except Exception as e:
        print(f"\n❌ 安装过程中出现错误: {e}")
        print("\n🔧 请尝试手动安装核心依赖:")
        print("pip install backtrader pandas numpy python-binance plotly jinja2 inquirer scipy")