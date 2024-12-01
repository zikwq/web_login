import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import requests
from bs4 import BeautifulSoup
import threading
from tkinter import ttk
import concurrent.futures
import re
import time
from datetime import timedelta
import queue
import os

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ssss/58.0.3029.110 Safari/537.3'
}

class LoginTool:
    def __init__(self, root):
        self.root = root
        self.root.title("登录尝试器")
        self.root.geometry("800x700")  # 增加窗口大小
        
        self.total_usernames = 0
        self.total_passwords = 0
        self.current_username = 0
        self.current_password = 0
        self.is_running = False
        self.start_time = None
        self.result_queue = queue.Queue()
        self.checkpoint_file = 'login_checkpoint.txt'
        self.cache_file = 'login_cache.txt'
        
        self.setup_ui()
    
    def setup_ui(self):
        # 创建主框架
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 配置网格权重，使控件均匀分布
        main_frame.columnconfigure(1, weight=1)

        # 创建输入框和标签
        labels_and_entries = [
            ("URL:", "url_entry"),
            ("用户名文件:", "username_entry", "choose_username_file"),
            ("用户名 (可选):", "username_input_entry"),
            ("跳过用户名正则 (可选):", "skip_keyword_entry"),
            ("密码文件:", "password_entry", "choose_password_file"),
            ("验证失败关键词 (可选):", "success_keyword_entry")
        ]
        
        for i, (label_text, entry_name, *button_cmd) in enumerate(labels_and_entries):
            tk.Label(main_frame, text=label_text, anchor='e').grid(row=i, column=0, sticky='e', padx=(0,10), pady=5)
            entry = tk.Entry(main_frame, width=50)
            entry.grid(row=i, column=1, sticky='ew', pady=5)
            setattr(self, entry_name, entry)
            
            if button_cmd:
                tk.Button(main_frame, text="选择文件", command=getattr(self, button_cmd[0])).grid(row=i, column=2, padx=5, sticky='w')
        
        # 线程数量
        tk.Label(main_frame, text="线程数量:", anchor='e').grid(row=len(labels_and_entries), column=0, sticky='e', padx=(0,10), pady=5)
        self.thread_count_entry = tk.Entry(main_frame, width=10)
        self.thread_count_entry.grid(row=len(labels_and_entries), column=1, sticky='w', pady=5)
        self.thread_count_entry.insert(0, "4")
        
        # 状态标签
        self.status_label = tk.Label(main_frame, text="用户名/密码: 0/0 / 0/0")
        self.status_label.grid(row=len(labels_and_entries)+1, column=0, columnspan=3, sticky='ew', pady=5)
        
        # 进度条
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', length=400, mode='determinate')
        self.progress_bar.grid(row=len(labels_and_entries)+2, column=0, columnspan=3, sticky='ew', padx=10, pady=5)
        
        # 按钮
        button_frame = tk.Frame(main_frame)
        button_frame.grid(row=len(labels_and_entries)+3, column=0, columnspan=3, sticky='ew', pady=5)
        
        tk.Button(button_frame, text="开始登录", command=self.start_login).pack(side=tk.LEFT, padx=10)
        self.stop_button = tk.Button(button_frame, text="停止", command=self.stop_login, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10)
        self.continue_button = tk.Button(button_frame, text="继续", command=self.continue_login, state=tk.DISABLED)
        self.continue_button.pack(side=tk.LEFT, padx=10)
        self.clear_cache_button = tk.Button(button_frame, text="清除缓存", command=self.clear_cache, state=tk.NORMAL)
        self.clear_cache_button.pack(side=tk.LEFT, padx=10)
        
        # 输出文本框
        self.output_text = scrolledtext.ScrolledText(main_frame, width=70, height=15)
        self.output_text.grid(row=len(labels_and_entries)+4, column=0, columnspan=3, sticky='nsew', padx=10, pady=10)
        
        # 配置主框架的网格权重，使文本框可以扩展
        main_frame.rowconfigure(len(labels_and_entries)+4, weight=1)
    
    def choose_username_file(self):
        filename = filedialog.askopenfilename(title="选择用户名文件", filetypes=[("Text files", "*.txt")])
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, filename)
    
    def choose_password_file(self):
        filename = filedialog.askopenfilename(title="选择密码文件", filetypes=[("Text files", "*.txt")])
        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, filename)
    
    def login(self, url, username, password):
        username = username.strip()
        password = password.strip()
        
        try:
            response = requests.post(url, data={'log': username, 'pwd': password}, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            return f"请求失败: {e}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.text
        
        skip_keyword = self.skip_keyword_entry.get()
        success_keyword = self.success_keyword_entry.get()
        
        if skip_keyword and re.search(skip_keyword, page_text):
            return f"用户名: {username} - 无效用户名，跳过"
        
        if success_keyword and re.search(success_keyword, page_text):
            return f"用户名: {username}, 密码: {password} - 登录失败"
        else:
            return f"用户名: {username}, 密码: {password} - ==================登录成功===================="
        
        return None
    
    def login_worker(self, url, username, passwords, start_index=0):
        results = []
        for i, password in enumerate(passwords[start_index:], start=start_index):
            if not self.is_running:
                return results, i
            
            result = self.login(url, username, password)
            if result:
                self.result_queue.put(result)
            
            # 记录当前进度到缓存文件
            with open(self.cache_file, 'w') as f:
                f.write(f"{username},{i}")
            
            with threading.Lock():
                self.current_password = i + 1
                progress = (self.current_password) / self.total_passwords * 100
                self.progress_bar['value'] = progress
                current_time = time.time()
                elapsed_time = current_time - self.start_time
                estimated_total_time = elapsed_time / progress * 100 if progress > 0 else 0
                remaining_time = max(0, estimated_total_time - elapsed_time)
                
                self.status_label.config(text=(
                    f"用户名: {username} 密码: {self.current_password}/{self.total_passwords} "
                    f"耗时: {timedelta(seconds=int(elapsed_time))} "
                    f"预计剩余: {timedelta(seconds=int(remaining_time))}"
                ))
                self.root.update_idletasks()
            
        return results, len(passwords)
    
    def start_login(self):
        url = self.url_entry.get()
        username_file = self.username_entry.get()
        password_file = self.password_entry.get()
        username_input = self.username_input_entry.get()
        thread_count = int(self.thread_count_entry.get())
        
        if not url or not password_file:
            messagebox.showerror("错误", "请确保URL和文件已选择")
            return
        
        with open(password_file, 'r') as f:
            passwords = [p.strip() for p in f.readlines()]
        
        usernames = [username_input] if username_input else []
        if not usernames:
            with open(username_file, 'r') as f:
                usernames = [u.strip() for u in f.readlines()]
        
        self.total_usernames = len(usernames)
        self.total_passwords = len(passwords)
        self.current_username = 0
        self.current_password = 0
        self.is_running = True
        self.start_time = time.time()
        
        self.stop_button.config(state=tk.NORMAL)
        self.continue_button.config(state=tk.DISABLED)
        self.output_text.delete(1.0, tk.END)
        
        # 启动结果打印线程
        self.start_result_printer()
        
        def run_login_thread():
            try:
                for username in usernames:
                    if not self.is_running:
                        break
                    
                    # 检查缓存文件
                    start_index = 0
                    if os.path.exists(self.cache_file):
                        with open(self.cache_file, 'r') as f:
                            saved_data = f.read().strip().split(',')
                            if len(saved_data) == 2 and saved_data[0] == username:
                                start_index = int(saved_data[1]) + 1
                    
                    results, last_password_index = self.login_worker(url, username, passwords, start_index)
                    
                    self.current_username += 1
            except Exception as e:
                self.result_queue.put(f"错误: {e}")
            finally:
                self.stop_login()
        
        threading.Thread(target=run_login_thread, daemon=True).start()
    
    def start_result_printer(self):
        def print_results():
            while self.is_running:
                try:
                    result = self.result_queue.get(timeout=1)
                    self.output_text.insert(tk.END, result + "\n")
                    self.output_text.see(tk.END)
                    self.root.update_idletasks()
                except queue.Empty:
                    continue
        
        threading.Thread(target=print_results, daemon=True).start()
    
    def stop_login(self):
        self.is_running = False
        self.stop_button.config(state=tk.DISABLED)
        self.continue_button.config(state=tk.NORMAL)
        
        current_time = time.time()
        total_time = current_time - self.start_time
        self.output_text.insert(tk.END, f"\n总耗时: {timedelta(seconds=int(total_time))}\n")
    
    def continue_login(self):
        self.start_login()
    
    def clear_cache(self):
        # 清除检查点和缓存文件
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            
            # 重置界面状态
            self.current_username = 0
            self.current_password = 0
            self.progress_bar['value'] = 0
            self.status_label.config(text="用户名/密码: 0/0 / 0/0")
            
            messagebox.showinfo("提示", "缓存已清除")
        except Exception as e:
            messagebox.showerror("错误", f"清除缓存失败: {e}")

# 创建主窗口
root = tk.Tk()
login_tool = LoginTool(root)
root.mainloop()