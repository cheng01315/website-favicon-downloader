import os
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
from favicon_core import FaviconDownloader

class FaviconDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("网站图标下载器")
        self.root.geometry("700x500")
        
        # 创建界面元素
        self.create_widgets()
        
        # 初始化下载器
        self.downloader = None
    
    def create_widgets(self):
        # 文件选择区域
        file_frame = ttk.Frame(self.root)
        file_frame.pack(padx=10, pady=10, fill=tk.X)
        
        ttk.Label(file_frame, text="选择域名文件:").pack(anchor=tk.W)
        
        file_input_frame = ttk.Frame(file_frame)
        file_input_frame.pack(fill=tk.X, pady=5)
        
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_input_frame, textvariable=self.file_path_var, state="readonly")
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_input_frame, text="浏览", command=self.browse_file).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 控制按钮区域
        button_frame = ttk.Frame(self.root)
        button_frame.pack(padx=10, pady=5, fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="开始下载", command=self.start_download)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
        # 进度条
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(padx=10, pady=10, fill=tk.X)
        
        ttk.Label(progress_frame, text="进度:").pack(anchor=tk.W)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)
        self.status_label.pack(padx=10, pady=5, anchor=tk.W)
        
        # 日志显示区域
        log_frame = ttk.Frame(self.root)
        log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        ttk.Label(log_frame, text="日志信息:").pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # 下载状态
        self.is_downloading = False
        self.download_thread = None
    
    def browse_file(self):
        """浏览并选择文件"""
        file_path = filedialog.askopenfilename(
            title="选择域名文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if file_path:
            self.file_path_var.set(file_path)
    
    def log_message(self, message):
        """在日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # 自动滚动到底部
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()  # 强制更新界面
    
    def progress_callback(self, current, total):
        """进度回调函数"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            self.status_var.set(f"正在下载... ({current}/{total})")
    
    def start_download(self):
        """开始下载"""
        file_path = self.file_path_var.get()
        
        if not file_path:
            self.log_message("请先选择域名文件")
            return
        
        if not os.path.exists(file_path):
            self.log_message(f"文件不存在: {file_path}")
            return
        
        # 禁用开始按钮，启用停止按钮
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_downloading = True
        
        # 清空之前的日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # 重置进度条
        self.progress_var.set(0)
        
        # 在新线程中运行下载
        self.download_thread = threading.Thread(target=self.run_download, args=(file_path,))
        self.download_thread.start()
    
    def run_download(self, file_path):
        """在后台线程中运行下载"""
        try:
            # 创建下载器实例，传入日志和进度回调
            self.downloader = FaviconDownloader(log_callback=self.log_message)
            
            # 开始处理文件
            self.downloader.process_domains_file(file_path, progress_callback=self.progress_callback)
            
            # 下载完成后更新界面
            self.download_complete()
        except Exception as e:
            self.log_message(f"下载过程中发生错误: {e}")
            self.download_complete()
    
    def stop_download(self):
        """停止下载"""
        self.is_downloading = False
        self.log_message("正在停止下载...")
    
    def download_complete(self):
        """下载完成后的处理"""
        # 更新界面状态
        self.root.after(0, self._update_ui_after_download)
    
    def _update_ui_after_download(self):
        """在下载完成后更新UI（在主线程中执行）"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(100)
        self.status_var.set("下载完成")
        self.log_message("所有任务已完成！")

if __name__ == "__main__":
    root = tk.Tk()
    app = FaviconDownloaderGUI(root)
    root.mainloop()