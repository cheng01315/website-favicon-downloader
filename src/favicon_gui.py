import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
from pathlib import Path
from favicon_core import (
    FaviconDownloader,
    LANGUAGES,
    DEFAULT_LANG,
    FORMAT_LABELS,
    FORMAT_ORDER,
    DEFAULT_FORMAT,
    DEFAULT_WORKERS,
    VERSION,
    detect_system_lang,
    format_label,
    tr,
)

# 线程数可选项
WORKER_CHOICES = ["1", "2", "3", "4", "5", "6", "8", "10", "16"]
SETTINGS_FILE = "favicon_settings.json"

# 界面文案
GUI_STRINGS = {
    "zh": {
        "title": "网站图标下载器 {version}",
        "file_label": "选择域名文件:",
        "browse": "浏览",
        "settings": "下载设置",
        "lang_label": "语言:",
        "workers_label": "线程数:",
        "format_label": "保存格式:",
        "hint": "线程越多越快，但可能被接口限流；格式转换只换格式，不改变图片尺寸",
        "start": "开始下载",
        "stop": "停止",
        "progress": "进度:",
        "log": "日志信息:",
        "ready": "就绪",
        "downloading": "正在下载... ({current}/{total})",
        "need_file": "请先选择域名文件",
        "file_missing": "文件不存在: {path}",
        "stopping": "正在停止下载...（已完成的图标会保留）",
        "stopping_status": "正在停止...",
        "stopped": "已停止",
        "stopped_log": "已停止，未处理的域名没有下载",
        "done": "下载完成",
        "all_done": "所有任务已完成！",
        "run_error": "下载过程中发生错误: {error}",
        "dialog_title": "选择域名文件",
        "filetype_txt": "文本文件",
        "filetype_all": "所有文件",
    },
    "en": {
        "title": "Website Favicon Downloader {version}",
        "file_label": "Domain list file:",
        "browse": "Browse",
        "settings": "Download settings",
        "lang_label": "Language:",
        "workers_label": "Threads:",
        "format_label": "Output format:",
        "hint": "More threads means faster, but the APIs may rate-limit you; conversion only changes the format, not the image size",
        "start": "Start",
        "stop": "Stop",
        "progress": "Progress:",
        "log": "Log:",
        "ready": "Ready",
        "downloading": "Downloading... ({current}/{total})",
        "need_file": "Please choose a domain file first",
        "file_missing": "File not found: {path}",
        "stopping": "Stopping... (icons already downloaded are kept)",
        "stopping_status": "Stopping...",
        "stopped": "Stopped",
        "stopped_log": "Stopped. Domains that were not processed have no icon.",
        "done": "Done",
        "all_done": "All tasks finished!",
        "run_error": "Error during download: {error}",
        "dialog_title": "Choose a domain file",
        "filetype_txt": "Text files",
        "filetype_all": "All files",
    },
}


def settings_path():
    """设置文件放在程序旁边（打包后就是 exe 所在目录）"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / SETTINGS_FILE


class FaviconDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.settings_path = settings_path()
        self.saved_settings = self.load_settings()

        # 界面语言：优先用上次的选择，没有就按系统语言决定，窗口里还能随时切
        saved_lang = self.saved_settings.get("lang")
        self.lang = saved_lang if saved_lang in LANGUAGES else detect_system_lang()

        # 当前保存格式（内部标识，与界面语言无关）
        self.format_key = self._normalize_format(self.saved_settings.get("format"))

        # 状态栏状态，切语言时用来重新渲染
        self.status_state = ("ready", {})

        self.create_widgets()
        self.retranslate()
        self._apply_window_icon()

        # 初始化下载器
        self.downloader = None

    def _apply_window_icon(self):
        """把窗口和任务栏图标也换成程序图标（打包后图标在 _MEIPASS 里）"""
        try:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            icon_path = base / "favicon_gui.ico"
            if icon_path.exists():
                # default= 让对话框等子窗口也用同一个图标
                self.root.iconbitmap(default=str(icon_path))
        except Exception:
            pass

    def gt(self, key, **kwargs):
        """按当前语言取界面文案"""
        table = GUI_STRINGS.get(self.lang) or GUI_STRINGS[DEFAULT_LANG]
        template = table.get(key) or GUI_STRINGS[DEFAULT_LANG].get(key, key)
        return template.format(**kwargs) if kwargs else template

    @staticmethod
    def _normalize_format(value):
        """把设置文件里的格式值转成内部标识（兼容早期存显示名的版本）"""
        if value in FORMAT_LABELS:
            return value
        for key, labels in FORMAT_LABELS.items():
            if value in labels.values():
                return key
        return DEFAULT_FORMAT

    def create_widgets(self):
        # 文件选择区域
        file_frame = ttk.Frame(self.root)
        file_frame.pack(padx=10, pady=(10, 5), fill=tk.X)

        self.file_label = ttk.Label(file_frame)
        self.file_label.pack(anchor=tk.W)

        file_input_frame = ttk.Frame(file_frame)
        file_input_frame.pack(fill=tk.X, pady=5)

        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_input_frame, textvariable=self.file_path_var, state="readonly")
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.browse_button = ttk.Button(file_input_frame, command=self.browse_file)
        self.browse_button.pack(side=tk.RIGHT, padx=(5, 0))

        # 下载设置区域
        self.settings_frame = ttk.LabelFrame(self.root)
        self.settings_frame.pack(padx=10, pady=5, fill=tk.X)

        self.lang_label = ttk.Label(self.settings_frame)
        self.lang_label.grid(row=0, column=0, padx=(10, 5), pady=8, sticky=tk.W)

        self.lang_var = tk.StringVar(value=LANGUAGES[self.lang])
        self.lang_box = ttk.Combobox(
            self.settings_frame, textvariable=self.lang_var,
            values=list(LANGUAGES.values()), width=8, state="readonly"
        )
        self.lang_box.grid(row=0, column=1, padx=(0, 20), pady=8, sticky=tk.W)
        self.lang_box.bind("<<ComboboxSelected>>", self.on_language_change)

        self.workers_label = ttk.Label(self.settings_frame)
        self.workers_label.grid(row=0, column=2, padx=(0, 5), pady=8, sticky=tk.W)

        saved_workers = str(self.saved_settings.get("workers", DEFAULT_WORKERS))
        if saved_workers not in WORKER_CHOICES:
            saved_workers = str(DEFAULT_WORKERS)
        self.workers_var = tk.StringVar(value=saved_workers)
        self.workers_box = ttk.Combobox(
            self.settings_frame, textvariable=self.workers_var, values=WORKER_CHOICES,
            width=5, state="readonly"
        )
        self.workers_box.grid(row=0, column=3, padx=(0, 20), pady=8, sticky=tk.W)

        self.format_label_widget = ttk.Label(self.settings_frame)
        self.format_label_widget.grid(row=0, column=4, padx=(0, 5), pady=8, sticky=tk.W)

        self.format_var = tk.StringVar()
        self.format_box = ttk.Combobox(
            self.settings_frame, textvariable=self.format_var, width=28, state="readonly"
        )
        self.format_box.grid(row=0, column=5, padx=(0, 10), pady=8, sticky=tk.W)
        self.format_box.bind("<<ComboboxSelected>>", self.on_format_change)

        self.hint_label = ttk.Label(self.settings_frame, foreground="#666666")
        self.hint_label.grid(row=1, column=0, columnspan=6, padx=10, pady=(0, 8), sticky=tk.W)

        # 控制按钮区域
        button_frame = ttk.Frame(self.root)
        button_frame.pack(padx=10, pady=5, fill=tk.X)

        self.start_button = ttk.Button(button_frame, command=self.start_download)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(button_frame, command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        # 进度条
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(padx=10, pady=10, fill=tk.X)

        self.progress_label = ttk.Label(progress_frame)
        self.progress_label.pack(anchor=tk.W)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)

        # 状态标签
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)
        self.status_label.pack(padx=10, pady=5, anchor=tk.W)

        # 日志显示区域
        log_frame = ttk.Frame(self.root)
        log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.log_label = ttk.Label(log_frame)
        self.log_label.pack(anchor=tk.W)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # 下载状态
        self.is_downloading = False
        self.download_thread = None

    def retranslate(self):
        """按当前语言刷新界面上的所有文字（切换语言、启动时都会调用）"""
        self.root.title(self.gt("title", version=VERSION))
        self.file_label.config(text=self.gt("file_label"))
        self.browse_button.config(text=self.gt("browse"))
        self.settings_frame.config(text=self.gt("settings"))
        self.lang_label.config(text=self.gt("lang_label"))
        self.workers_label.config(text=self.gt("workers_label"))
        self.format_label_widget.config(text=self.gt("format_label"))
        self.hint_label.config(text=self.gt("hint"))
        self.start_button.config(text=self.gt("start"))
        self.stop_button.config(text=self.gt("stop"))
        self.progress_label.config(text=self.gt("progress"))
        self.log_label.config(text=self.gt("log"))

        self.lang_var.set(LANGUAGES[self.lang])

        # 下拉框的选项名要跟着语言换，但当前选中的格式保持不变
        self.format_box.config(values=[format_label(k, self.lang) for k in FORMAT_ORDER])
        self.format_var.set(format_label(self.format_key, self.lang))

        key, kwargs = self.status_state
        self.status_var.set(self.gt(key, **kwargs))

    def on_language_change(self, event=None):
        """切换界面语言"""
        selected = self.lang_var.get()
        for code, name in LANGUAGES.items():
            if name == selected:
                self.lang = code
                break
        self.retranslate()

    def on_format_change(self, event=None):
        """把界面上选的显示名转成内部标识"""
        label = self.format_var.get()
        for key in FORMAT_ORDER:
            if format_label(key, self.lang) == label:
                self.format_key = key
                return

    def browse_file(self):
        """浏览并选择文件"""
        file_path = filedialog.askopenfilename(
            title=self.gt("dialog_title"),
            filetypes=[
                (self.gt("filetype_txt"), "*.txt"),
                (self.gt("filetype_all"), "*.*"),
            ]
        )

        if file_path:
            self.file_path_var.set(file_path)

    def load_settings(self):
        """读取上次用的语言、线程数和格式"""
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_settings(self):
        """记住这次的选择，下次打开程序还是这个语言、线程数和格式"""
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "lang": self.lang,
                        "workers": self.workers_var.get(),
                        "format": self.format_key,
                    },
                    f, ensure_ascii=False, indent=2,
                )
        except Exception:
            pass

    # ---- 下面几个方法可能被工作线程调用，一律转回主线程执行 ----

    def log_message(self, message):
        """在日志区域添加消息"""
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # 自动滚动到底部
        self.log_text.config(state=tk.DISABLED)

    def progress_callback(self, current, total):
        """进度回调函数"""
        self.root.after(0, self._update_progress, current, total)

    def _update_progress(self, current, total):
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            self.set_status("downloading", current=current, total=total)

    def set_status(self, key, **kwargs):
        """设置状态栏文字（记住 key，切语言时能重新渲染）"""
        self.status_state = (key, kwargs)
        self.status_var.set(self.gt(key, **kwargs))

    def _set_running(self, running):
        """运行期间锁定/解锁控件"""
        self.is_downloading = running
        self.start_button.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if running else tk.DISABLED)
        state = "disabled" if running else "readonly"
        self.lang_box.config(state=state)
        self.workers_box.config(state=state)
        self.format_box.config(state=state)

    def start_download(self):
        """开始下载"""
        file_path = self.file_path_var.get()

        if not file_path:
            self.log_message(self.gt("need_file"))
            return

        if not os.path.exists(file_path):
            self.log_message(self.gt("file_missing", path=file_path))
            return

        # 记住这次的选择
        self.save_settings()

        # 锁定控件
        self._set_running(True)

        # 清空之前的日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # 重置进度条
        self.progress_var.set(0)

        # 在主线程里建好下载器，再交给工作线程使用
        self.downloader = FaviconDownloader(
            log_callback=self.log_message,
            output_format=self.format_key,
            lang=self.lang,
        )

        max_workers = int(self.workers_var.get())

        # 在新线程中运行下载
        self.download_thread = threading.Thread(
            target=self.run_download, args=(file_path, max_workers), daemon=True
        )
        self.download_thread.start()

    def run_download(self, file_path, max_workers):
        """在后台线程中运行下载"""
        stopped = False
        try:
            self.downloader.process_domains_file(
                file_path,
                progress_callback=self.progress_callback,
                max_workers=max_workers,
            )
            stopped = self.downloader.stop_event.is_set()
        except Exception as e:
            self.log_message(self.gt("run_error", error=e))

        # 下载完成后更新界面
        self.root.after(0, self._update_ui_after_download, stopped)

    def stop_download(self):
        """停止下载"""
        if self.downloader:
            self.downloader.stop()
        self.log_message(self.gt("stopping"))
        self.set_status("stopping_status")

    def _update_ui_after_download(self, stopped=False):
        """在下载完成后更新UI（在主线程中执行）"""
        self._set_running(False)
        if stopped:
            self.set_status("stopped")
            self.log_message(self.gt("stopped_log"))
        else:
            self.progress_var.set(100)
            self.set_status("done")
            self.log_message(self.gt("all_done"))


if __name__ == "__main__":
    root = tk.Tk()
    app = FaviconDownloaderGUI(root)
    root.mainloop()
