#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易记录爬取脚本 - 手动翻页版本
用于获取交易平台的所有交易记录并保存为CSV文件
"""

import csv
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class TradingRecordScraper:
    def __init__(self, url, headless=False):
        """
        初始化爬虫
        :param url: 目标网址
        :param headless: 是否使用无头模式
        """
        self.url = url
        self.driver = None
        self.records = []
        self.setup_driver(headless)
    
    def setup_driver(self, headless):
        """设置WebDriver"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 添加用户代理
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def get_current_page_number(self):
        """获取当前页码"""
        try:
            # 查找当前激活的页码
            active_page = self.driver.find_element(By.CSS_SELECTOR, ".bn-pagination-item.active")
            page_text = active_page.text.strip()
            
            if page_text.isdigit():
                return int(page_text)
            
            # 备用方案：查找aria-current='page'
            try:
                current_page = self.driver.find_element(By.CSS_SELECTOR, "[aria-current='page']")
                page_text = current_page.text.strip()
                if page_text.isdigit():
                    return int(page_text)
            except:
                pass
                
            return 1  # 默认第1页
        except Exception as e:
            print(f"⚠️ 获取当前页码失败: {e}")
            return 1
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 查找最后一个页码按钮
            page_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".bn-pagination-item")
            
            max_page = 1
            for btn in page_buttons:
                btn_text = btn.text.strip()
                if btn_text.isdigit():
                    max_page = max(max_page, int(btn_text))
            
            # 也可以查找"84"这样的最大页码
            if max_page == 1:
                # 尝试查找包含数字的文本
                page_info_elements = self.driver.find_elements(By.CSS_SELECTOR, "*")
                for element in page_info_elements:
                    text = element.text.strip()
                    # 查找类似"第1页，共84页"的文本
                    match = re.search(r'共\s*(\d+)\s*页', text)
                    if match:
                        return int(match.group(1))
                    
                    # 查找页码序列，找最大的数字
                    if re.match(r'^\d+$', text) and len(text) <= 3:
                        try:
                            page_num = int(text)
                            if 50 <= page_num <= 999:  # 假设总页数在这个范围
                                max_page = max(max_page, page_num)
                        except:
                            pass
            
            return max_page if max_page > 1 else 84  # 默认84页（从截图看到的）
            
        except Exception as e:
            print(f"⚠️ 获取总页数失败: {e}")
            return 84  # 默认值
    
    def wait_for_page_change(self, current_page, timeout=300):
        """
        等待页面变化（用户手动翻页）
        :param current_page: 当前页码
        :param timeout: 超时时间（秒）
        :return: 新的页码，如果超时返回None
        """
        print(f"\n⏳ 等待页面变化...")
        print(f"📖 当前页: {current_page}")
        print(f"🖱️  请手动点击翻页按钮...")
        print(f"⏰ 程序将自动检测页面变化（超时时间: {timeout}秒）")
        print(f"💡 如果已是最后一页，请等待程序自动退出，或按 Ctrl+C 停止")
        
        start_time = time.time()
        check_interval = 1  # 每秒检查一次
        
        while time.time() - start_time < timeout:
            try:
                # 检查页码是否变化
                new_page = self.get_current_page_number()
                
                if new_page != current_page:
                    print(f"✅ 检测到页面变化: {current_page} → {new_page}")
                    # 等待数据加载完成
                    time.sleep(3)
                    return new_page
                
                # 检查是否还有下一页按钮可用
                try:
                    next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                        ".bn-pagination-item:not(.disabled):last-child")
                    if not next_buttons:
                        print("ℹ️ 未找到可用的下一页按钮，可能已到最后一页")
                        return None
                except:
                    pass
                
                time.sleep(check_interval)
                
                # 每30秒提示一次
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    remaining = timeout - elapsed
                    print(f"⏳ 仍在等待翻页... (剩余 {int(remaining)} 秒)")
                
            except KeyboardInterrupt:
                print("\n⏹️ 用户中断等待")
                return None
            except Exception as e:
                print(f"⚠️ 检测页面变化时出错: {e}")
                time.sleep(check_interval)
        
        print(f"⏰ 等待超时（{timeout}秒），停止检测")
        return None
    
    def extract_record_from_row(self, row_element):
        """
        从表格行元素中提取交易记录
        :param row_element: 表格行元素
        :return: 交易记录字典
        """
        try:
            # 这种表格结构：每行只有一个大的td，数据在内部div中组织
            
            # 1. 提取交易对符号
            symbol = ""
            try:
                symbol_element = row_element.find_element(By.CSS_SELECTOR, ".t-subtitle1.text-PrimaryText")
                symbol = symbol_element.text.strip()
            except:
                # 备用方案：从文本中提取
                row_text = row_element.text
                symbol_match = re.search(r'([A-Z]+USDT?)', row_text)
                symbol = symbol_match.group(1) if symbol_match else "UNKNOWN"
            
            # 2. 提取交易方向
            direction = "Long"  # 默认做多
            try:
                # 查找做多/做空标签
                direction_element = row_element.find_element(By.CSS_SELECTOR, ".bn-bubble__success .bn-bubble-content")
                direction_text = direction_element.text.strip()
                if "做空" in direction_text or "空" in direction_text:
                    direction = "Short"
                elif "做多" in direction_text or "多" in direction_text:
                    direction = "Long"
            except:
                pass
            
            # 3. 提取各个数据字段 - 使用更精确的选择器
            data_fields = {}
            
            # 获取所有数据容器
            data_containers = row_element.find_elements(By.CSS_SELECTOR, ".w-\\[calc\\(20\\%-13px\\)\\]")
            
            for container in data_containers:
                try:
                    # 获取字段标题和值
                    label_element = container.find_element(By.CSS_SELECTOR, ".t-caption2.text-SecondaryText")
                    value_element = container.find_element(By.CSS_SELECTOR, ".t-caption2.text-PrimaryText")
                    
                    label = label_element.text.strip()
                    value = value_element.text.strip()
                    
                    if label and value:
                        data_fields[label] = value
                        
                except:
                    continue
            
            # 4. 从数据字段中提取具体信息
            entry_time = data_fields.get('开仓时间', '')
            entry_price = self.extract_number(data_fields.get('开仓价格', ''))
            max_position = self.extract_number(data_fields.get('最大持仓量', ''))
            exit_time = data_fields.get('全部平仓', '')
            exit_price = self.extract_number(data_fields.get('平仓均价', ''))
            
            # 5. 提取盈亏信息
            profit_loss = ""
            try:
                profit_element = row_element.find_element(By.CSS_SELECTOR, ".text-Buy, .text-Sell")
                profit_loss = profit_element.text.strip()
            except:
                profit_loss = data_fields.get('平仓盈亏', '')
            
            profit_loss = self.extract_profit_loss(profit_loss)
            
            # 6. 计算持仓时长
            hold_duration = self.calculate_duration(entry_time, exit_time)
            
            # 7. 计算盈亏百分比
            profit_pct = self.calculate_profit_percentage(profit_loss, entry_price, max_position)
            
            record = {
                'symbol': symbol,
                'interval': '1d',
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': direction,
                'profit_loss': profit_loss,
                'profit_pct': profit_pct,
                'hold_duration': hold_duration,
                'exit_reason': 'Manual'
            }
            
            return record
            
        except Exception as e:
            print(f"提取记录时出错: {e}")
            return None
    
    def parse_datetime(self, datetime_str):
        """解析日期时间字符串"""
        if not datetime_str:
            return ''
        
        try:
            # 匹配格式：2025-05-22 06:56:53
            if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', datetime_str):
                return datetime_str
            
            # 其他可能的日期格式处理
            return datetime_str
        except:
            return datetime_str
    
    def extract_number(self, text):
        """从文本中提取数字"""
        if not text:
            return ''
        
        # 移除非数字字符，保留小数点
        number_match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
        return number_match.group() if number_match else ''
    
    def extract_profit_loss(self, text):
        """提取盈亏数值"""
        if not text:
            return ''
        
        # 匹配包含正负号的数字
        profit_match = re.search(r'[+-]?[\d,]+\.?\d*', text)
        return profit_match.group() if profit_match else ''
    
    def determine_direction(self, row_element, profit_loss):
        """根据行样式或盈亏判断交易方向"""
        try:
            # 检查盈亏文本的颜色
            profit_element = row_element.find_elements(By.CSS_SELECTOR, "[style*='color']")
            
            if profit_loss and isinstance(profit_loss, str):
                if profit_loss.startswith('+'):
                    return 'Long'
                elif profit_loss.startswith('-'):
                    return 'Short'
            
            # 默认返回
            return 'Long'
        except:
            return 'Long'
    
    def calculate_duration(self, entry_time, exit_time):
        """计算持仓时长"""
        if not entry_time or not exit_time:
            return ''
        
        try:
            entry_dt = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S')
            exit_dt = datetime.strptime(exit_time, '%Y-%m-%d %H:%M:%S')
            duration = exit_dt - entry_dt
            
            days = duration.days
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except:
            return ''
    
    def calculate_profit_percentage(self, profit_loss, entry_price, position_size):
        """计算盈亏百分比"""
        try:
            if not all([profit_loss, entry_price, position_size]):
                return ''
            
            profit_num = float(str(profit_loss).replace('+', '').replace(',', ''))
            entry_num = float(str(entry_price).replace(',', ''))
            position_num = float(str(position_size).replace(',', ''))
            
            if entry_num > 0 and position_num > 0:
                invested = entry_num * position_num
                pct = (profit_num / invested) * 100
                return f"{pct:.2f}%"
        except:
            pass
        
        return ''
    
    def scrape_current_page(self):
        """爬取当前页面的交易记录"""
        try:
            print("⏳ 等待页面数据加载...")
            # 等待表格行加载
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr.bn-web-table-row"))
            )
            
            # 额外等待确保数据完全加载
            time.sleep(2)
            
            # 获取所有数据行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "tr.bn-web-table-row")
            print(f"📊 找到 {len(rows)} 行数据")
            
            if not rows:
                print("❌ 没有找到任何数据行")
                return []
            
            page_records = []
            
            # 逐行处理
            for i, row in enumerate(rows):
                try:
                    # 检查行是否包含有效数据
                    row_text = row.text.strip()
                    if not row_text or len(row_text) < 10:
                        continue
                    
                    # 检查是否包含交易对信息
                    if not re.search(r'[A-Z]+USDT?', row_text):
                        continue
                    
                    record = self.extract_record_from_row(row)
                    if record:
                        page_records.append(record)
                        print(f"✅ 记录 {i+1}: {record['symbol']} | {record['direction']} | 盈亏: {record['profit_loss']}")
                        
                except Exception as e:
                    print(f"❌ 处理第 {i+1} 行时出错: {e}")
                    continue
            
            print(f"📋 本页共提取到 {len(page_records)} 条有效记录")
            return page_records
            
        except TimeoutException:
            print("⏰ 页面加载超时")
            return []
        except Exception as e:
            print(f"❌ 爬取当前页面时出错: {e}")
            return []
    
    def scrape_all_pages_manual(self):
        """手动翻页模式：爬取所有页面的交易记录"""
        print("🚀 开始手动翻页模式爬取交易记录...")
        print("📖 程序将检测页面变化，请手动点击翻页按钮")
        
        # 打开网页
        self.driver.get(self.url)
        time.sleep(5)  # 等待页面完全加载
        
        # 获取总页数和当前页
        total_pages = self.get_total_pages()
        current_page = self.get_current_page_number()
        
        print(f"📄 检测到总页数: {total_pages}")
        print(f"📖 当前页码: {current_page}")
        
        total_records = 0
        
        while current_page <= total_pages:
            print(f"\n" + "="*60)
            print(f"📖 正在处理第 {current_page} 页 (共 {total_pages} 页)")
            print(f"📊 已收集记录: {total_records} 条")
            print("="*60)
            
            # 爬取当前页面
            page_records = self.scrape_current_page()
            
            if page_records:
                self.records.extend(page_records)
                total_records += len(page_records)
                print(f"✅ 第 {current_page} 页获取到 {len(page_records)} 条记录")
                
                # 保存中间结果（防止数据丢失）
                if total_records % 50 == 0:  # 每50条记录保存一次
                    self.save_to_csv(f'trade_records_backup_{total_records}.csv')
                    print(f"💾 已保存备份文件（{total_records}条记录）")
            else:
                print(f"⚠️ 第 {current_page} 页没有找到记录")
            
            # 检查是否为最后一页
            if current_page >= total_pages:
                print(f"🎉 已处理完所有页面（第 {total_pages} 页）")
                break
            
            # 等待用户手动翻页
            print(f"\n💡 请手动点击翻页按钮，跳转到第 {current_page + 1} 页")
            new_page = self.wait_for_page_change(current_page, timeout=300)
            
            if new_page is None:
                print("⏹️ 未检测到页面变化，停止爬取")
                break
            elif new_page <= current_page:
                print(f"⚠️ 页码没有增加（{current_page} → {new_page}），可能已到最后一页")
                break
            else:
                current_page = new_page
                print(f"✅ 页面已更新到第 {current_page} 页，继续抓取...")
        
        print(f"\n🎉 爬取完成！")
        print(f"📊 总共获取到 {total_records} 条交易记录")
        print(f"📄 处理了 {current_page} 页数据")
        
        return self.records
    
    def save_to_csv(self, filename='trade_records.csv'):
        """保存记录到CSV文件"""
        if not self.records:
            print("没有记录需要保存")
            return
        
        fieldnames = [
            'symbol', 'interval', 'entry_time', 'exit_time', 
            'entry_price', 'exit_price', 'direction', 'profit_loss', 
            'profit_pct', 'hold_duration', 'exit_reason'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.records)
        
        print(f"💾 记录已保存到 {filename}")
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()

def main():
    """主函数"""
    print("🎯 交易记录爬取工具 - 手动翻页版")
    print("="*60)
    
    # 获取网址
    url = input("请输入交易平台的网址: ").strip()
    
    if not url:
        print("❌ 请提供有效的网址")
        return
    
    # 询问是否使用无头模式
    headless_input = input("是否使用无头模式？(y/n，默认n): ").strip().lower()
    headless = headless_input in ['y', 'yes', '是']
    
    if headless:
        print("⚠️ 注意：无头模式下无法手动翻页，建议使用可视模式")
        confirm = input("确定使用无头模式吗？(y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '是']:
            headless = False
    
    scraper = TradingRecordScraper(url, headless=headless)
    
    try:
        print("\n🚀 开始运行...")
        print("💡 使用说明：")
        print("   1. 程序会自动分析页面结构")
        print("   2. 抓取当前页数据后，程序会提示您手动翻页")
        print("   3. 程序检测到页面变化后会自动继续抓取")
        print("   4. 重复此过程直到所有页面完成")
        print("   5. 按 Ctrl+C 可随时停止程序")
        
        # 使用手动翻页模式
        scraper.scrape_all_pages_manual()
        
        # 保存最终结果
        if scraper.records:
            scraper.save_to_csv('trade_records_final.csv')
            print(f"\n✅ 最终结果已保存到 trade_records_final.csv")
            print(f"📊 总计 {len(scraper.records)} 条交易记录")
        else:
            print("⚠️ 没有找到任何交易记录")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
        if scraper.records:
            scraper.save_to_csv('trade_records_interrupted.csv')
            print(f"💾 已保存中断前的数据到 trade_records_interrupted.csv")
            print(f"📊 共 {len(scraper.records)} 条记录")
    except Exception as e:
        print(f"❌ 程序执行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
        if scraper.records:
            scraper.save_to_csv('trade_records_error.csv')
            print(f"💾 已保存出错前的数据到 trade_records_error.csv")
    finally:
        scraper.close()
        print("\n👋 程序结束")

if __name__ == "__main__":
    main()