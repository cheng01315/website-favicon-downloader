import os
import io
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from pathlib import Path

VERSION = "1.3"
BUILD_DATE = "2026-09-29"

# 界面语言 / UI languages
LANGUAGES = {
    "zh": "中文",
    "en": "English",
}
DEFAULT_LANG = "zh"


def detect_system_lang():
    """按系统语言挑默认界面语言：中文系统用中文，其它一律英文"""
    # Windows 上直接用系统 API，最准（能区分简体、繁体、地区）
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # LANGID 低 10 位是主语言 ID，0x04 即中文
        return "zh" if (lang_id & 0x3FF) == 0x04 else "en"
    except Exception:
        pass

    # 其它平台退回 locale
    try:
        import locale

        code = (locale.getlocale()[0] or "")
        if code.lower().startswith("zh") or "chinese" in code.lower():
            return "zh"
    except Exception:
        pass

    return "en"

# 保存格式：内部标识 -> 各语言下的显示名
FORMAT_LABELS = {
    "keep": {"zh": "保持原样（不转换）", "en": "Keep original (no conversion)"},
    "PNG": {"zh": "统一 PNG", "en": "Force PNG"},
    "ICO": {"zh": "统一 ICO", "en": "Force ICO"},
    "JPG": {"zh": "统一 JPG", "en": "Force JPG"},
}
FORMAT_ORDER = ["keep", "PNG", "ICO", "JPG"]
DEFAULT_FORMAT = "keep"
DEFAULT_WORKERS = 4

# 日志与提示文案
STRINGS = {
    "zh": {
        "run_version": "运行版本 {version}（{date}）",
        "start_summary": "共 {total} 个域名，线程数 {workers}，保存格式 {fmt}，输出目录 {dir}",
        "no_domains": "没有找到有效的域名",
        "file_missing": "错误：文件 {path} 不存在",
        "read_error": "读取文件时发生错误：{error}",
        "too_small": "警告: {domain} 的图标文件过小 ({size} 字节)，可能不是有效的图标",
        "only_svg": "提示: {domain} 只取到 SVG 矢量图，继续尝试后面的接口",
        "api_failed": "尝试API {url} 失败: {error}",
        "no_pillow": "未安装 Pillow，无法转换格式，已按原格式保存",
        "svg_convert": "SVG 是矢量图，Pillow 转不了位图，已按原格式保存",
        "image_broken": "图片无法解析（{error}），已按原格式保存",
        "convert_failed": "转换成 {fmt} 失败（{error}），已按原格式保存",
        "downloading": "正在下载 {domain} 的图标...",
        "removed_old": "已删除同域名的旧文件: {name}",
        "saved": "成功下载 {domain} 的图标: {path}",
        "save_failed": "保存图标失败 {domain}: {error}",
        "fetch_failed": "无法获取 {domain} 的图标",
        "task_error": "处理 {domain} 时出错: {error}",
        "done": "\n下载完成！",
        "ok_count": "成功: {n} 个",
        "fail_count": "失败: {n} 个",
        "stopped_note": "（任务被手动停止，以上是已完成的部分）",
        "exported": "结果已导出到 successful_downloads.txt 和 failed_downloads.txt",
        "csv_header": "域名,图标URL",
    },
    "en": {
        "run_version": "Version {version} ({date})",
        "start_summary": "{total} domains, {workers} threads, output format: {fmt}, output directory: {dir}",
        "no_domains": "No valid domains found",
        "file_missing": "Error: file {path} does not exist",
        "read_error": "Error while reading the file: {error}",
        "too_small": "Warning: the icon for {domain} is only {size} bytes, it may not be a valid icon",
        "only_svg": "Note: only got an SVG for {domain}, trying the next endpoint",
        "api_failed": "Endpoint {url} failed: {error}",
        "no_pillow": "Pillow is not installed, cannot convert; kept the original format",
        "svg_convert": "SVG is a vector format and Pillow cannot rasterise it; kept the original format",
        "image_broken": "Cannot decode the image ({error}); kept the original format",
        "convert_failed": "Conversion to {fmt} failed ({error}); kept the original format",
        "downloading": "Downloading icon for {domain}...",
        "removed_old": "Removed the previous file of this domain: {name}",
        "saved": "Saved icon for {domain}: {path}",
        "save_failed": "Failed to save the icon for {domain}: {error}",
        "fetch_failed": "Could not get an icon for {domain}",
        "task_error": "Error while processing {domain}: {error}",
        "done": "\nAll done!",
        "ok_count": "Succeeded: {n}",
        "fail_count": "Failed: {n}",
        "stopped_note": "(stopped manually, the lines above are what completed)",
        "exported": "Results exported to successful_downloads.txt and failed_downloads.txt",
        "csv_header": "domain,icon_url",
    },
}


def format_label(key, lang=DEFAULT_LANG):
    """取某个格式在指定语言下的显示名"""
    labels = FORMAT_LABELS.get(key, {})
    return labels.get(lang) or labels.get(DEFAULT_LANG) or key


def tr(lang, key, **kwargs):
    """取指定语言下的一段文案"""
    table = STRINGS.get(lang) or STRINGS[DEFAULT_LANG]
    template = table.get(key) or STRINGS[DEFAULT_LANG].get(key, key)
    return template.format(**kwargs) if kwargs else template


class FaviconDownloader:
    def __init__(self, log_callback=None, output_format=DEFAULT_FORMAT, lang=DEFAULT_LANG):
        self.website_ico_dir = Path("website_ico")
        self.website_ico_dir.mkdir(exist_ok=True)

        # requests.Session 不是线程安全的，每个线程各用一个
        self._local = threading.local()
        self._user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )

        self.output_format = output_format if output_format in FORMAT_LABELS else DEFAULT_FORMAT
        self.lang = lang if lang in LANGUAGES else DEFAULT_LANG
        self.stop_event = threading.Event()
        self.log_callback = log_callback  # 用于GUI的日志回调函数

        # 多个favicon获取API接口
        # 排序依据：优先用返回网站原图的接口（程序不改图，接口给什么就存什么），
        # 会重绘/放大的接口只作兜底。2026-09 大陆电信网络（福建）实测
        self.api_endpoints = [
            # ===== 返回网站原始图标，不缩放不重绘 =====
            "https://favicon.im/{}",  # favicon.im：原图，分辨率最高（实测最大936x946），约1.3s
            "https://api.xinac.net/icon/?url={}",  # 芯云API（国内节点）：原图，最快约100ms
            "https://favicon.cccyun.cc/{}",  # 彩虹云：原图，约100ms，但部分域名返回403或空响应
            # ===== 兜底：会重绘或放大，前面拿不到原图时才会用到 =====
            "https://icon.horse/icon/{}",  # Icon Horse：会把图重绘成256x256，约1.1s
            "https://favicon.yandex.net/favicon/{}/256",  # Yandex：只给16x32的合成小图
            # ===== 大陆直连不通，仅挂代理/海外环境时可用 =====
            "https://www.google.com/s2/favicons?domain={}&sz=256",  # Google favicon API
            "https://icons.duckduckgo.com/ip3/{}.ico",  # DuckDuckGo favicon API
        ]
        # 已移除 faviconkit：服务已停，会302到GitHub上一张1x1透明占位图

    def t(self, key, **kwargs):
        """按当前语言取文案"""
        return tr(self.lang, key, **kwargs)

    def _get_session(self):
        """取当前线程的 Session（没有就建一个）"""
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({'User-Agent': self._user_agent})
            self._local.session = session
        return session

    def stop(self):
        """请求停止：正在排队的域名会被跳过"""
        self.stop_event.set()

    def log_message(self, message):
        """发送日志消息到GUI"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def read_domains_from_file(self, file_path):
        """从txt文件读取网站域名列表"""
        domains = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    domain = line.strip()
                    if domain:  # 忽略空行
                        # 如果域名包含协议，仅提取域名部分
                        if '//' in domain:
                            parsed = urlparse(domain)
                            domain = parsed.netloc
                        domains.append(domain)
        except FileNotFoundError:
            self.log_message(self.t("file_missing", path=file_path))
        except Exception as e:
            self.log_message(self.t("read_error", error=e))

        return domains

    def get_favicon_url(self, domain):
        """尝试多个API获取网站图标URL"""
        svg_fallback = None
        # 选了位图格式（PNG/JPG/ICO）时，SVG 矢量图转不了，需要继续找能给位图的接口
        wants_bitmap = self.output_format in ("PNG", "JPG", "ICO")
        for api_url in self.api_endpoints:
            if self.stop_event.is_set():
                return None, None
            try:
                # 替换API URL中的域名
                url = api_url.format(domain)

                # 尝试下载图标
                response = self._get_session().get(url, timeout=10)
                if response.status_code == 200 and len(response.content) > 0:
                    # 检查响应是否为有效图像
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type or (content_type == '' and len(response.content) > 0):
                        # 检查是否为非常小的图像（可能是默认图标）
                        if len(response.content) < 100:  # 小于100字节可能是默认图标
                            self.log_message(self.t(
                                "too_small", domain=domain, size=len(response.content)))
                            continue
                        if wants_bitmap and self.is_svg(response.content):
                            # 先把 SVG 存着当兜底，继续往后找能转换成位图的接口
                            if svg_fallback is None:
                                svg_fallback = (url, response.content)
                            self.log_message(self.t("only_svg", domain=domain))
                            continue
                        return url, response.content
            except Exception as e:
                self.log_message(self.t("api_failed", url=api_url.format(domain), error=e))
                continue

        # 所有接口都只给了 SVG 时，退回用 SVG（后面按原格式保存）
        if svg_fallback:
            return svg_fallback
        return None, None

    def convert_to_format(self, content, target_format):
        """把图标转成指定格式，只换容器格式，不改变尺寸。
        返回 (扩展名, 字节内容)，转换不了则返回 None（调用方按原格式保存）"""
        try:
            from PIL import Image
        except ImportError:
            self.log_message(self.t("no_pillow"))
            return None

        try:
            image = Image.open(io.BytesIO(content))
            image.load()
        except Exception as e:
            if self.is_svg(content):
                self.log_message(self.t("svg_convert"))
            else:
                self.log_message(self.t("image_broken", error=e))
            return None

        buffer = io.BytesIO()
        try:
            if target_format == "PNG":
                if image.mode not in ("RGB", "RGBA", "P", "L"):
                    image = image.convert("RGBA")
                image.save(buffer, "PNG")
                return ".png", buffer.getvalue()

            if target_format == "JPG":
                # JPEG 不支持透明，转成 RGB 后按原尺寸保存
                image.convert("RGB").save(buffer, "JPEG", quality=95)
                return ".jpg", buffer.getvalue()

            if target_format == "ICO":
                # ICO 单边上限 256，超过就等比缩小，小于 256 的不放大
                width, height = image.size
                side = min(max(width, height), 256)
                if (width, height) == (side, side):
                    icon = image
                else:
                    ratio = side / max(width, height)
                    resized = image.resize(
                        (max(1, round(width * ratio)), max(1, round(height * ratio)))
                    )
                    icon = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                    icon.paste(
                        resized,
                        ((side - resized.size[0]) // 2, (side - resized.size[1]) // 2)
                    )
                icon.save(buffer, "ICO", sizes=[(side, side)])
                return ".ico", buffer.getvalue()
        except Exception as e:
            self.log_message(self.t("convert_failed", fmt=target_format, error=e))
            return None

        return None

    def download_favicon(self, domain):
        """下载单个网站的图标"""
        self.log_message(self.t("downloading", domain=domain))

        favicon_url, favicon_content = self.get_favicon_url(domain)

        if favicon_content:
            # 生成文件名，替换非法字符
            safe_domain = "".join(c for c in domain if c.isalnum() or c in ('.', '-')).rstrip()

            content = favicon_content
            file_extension = self.get_file_extension(favicon_content)

            # 只有选了统一格式才转换，默认保持接口返回的原格式、原尺寸
            if self.output_format != "keep":
                converted = self.convert_to_format(favicon_content, self.output_format)
                if converted:
                    file_extension, content = converted

            file_path = self.website_ico_dir / f"{safe_domain}{file_extension}"

            # 同一个域名只保留一个文件：清掉之前留下的其它扩展名（比如上一轮存的 .svg），
            # 否则新旧文件并存，会让人以为格式没有生效
            for old_file in self.website_ico_dir.glob(f"{safe_domain}.*"):
                if old_file != file_path:
                    try:
                        old_file.unlink()
                        self.log_message(self.t("removed_old", name=old_file.name))
                    except OSError:
                        pass

            try:
                with open(file_path, 'wb') as f:
                    f.write(content)
                self.log_message(self.t("saved", domain=domain, path=file_path))
                return True, favicon_url
            except Exception as e:
                self.log_message(self.t("save_failed", domain=domain, error=e))
                return False, favicon_url
        else:
            self.log_message(self.t("fetch_failed", domain=domain))
            return False, None

    def get_file_extension(self, content):
        """根据图像内容判断文件扩展名"""
        # 检查文件头来判断图像类型
        if content[:4] == b'\x89PNG':
            return '.png'
        elif content[:3] == b'\xff\xd8\xff':
            return '.jpg'
        elif content[:6] in [b'GIF87a', b'GIF89a']:
            return '.gif'
        elif content[:4] in (b'\x00\x00\x01\x00', b'\x00\x00\x02\x00'):
            return '.ico'
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            return '.webp'
        elif self.is_svg(content):
            return '.svg'
        else:
            # 默认使用PNG
            return '.png'

    def is_svg(self, content):
        """判断内容是不是 SVG（矢量图）"""
        return content[:400].lstrip(b'\xef\xbb\xbf \t\r\n').startswith((b'<svg', b'<?xml'))

    def process_domains_file(self, input_file, progress_callback=None, max_workers=1):
        """处理包含域名的txt文件"""
        domains = self.read_domains_from_file(input_file)

        if not domains:
            self.log_message(self.t("no_domains"))
            return [], []

        self.stop_event.clear()

        workers = max(1, int(max_workers))
        total_domains = len(domains)
        results = [None] * total_domains
        counter = {"done": 0}
        lock = threading.Lock()

        self.log_message(self.t("run_version", version=VERSION, date=BUILD_DATE))
        self.log_message(self.t(
            "start_summary",
            total=total_domains,
            workers=workers,
            fmt=format_label(self.output_format, self.lang),
            dir=self.website_ico_dir.resolve(),
        ))

        def handle(index, domain):
            if self.stop_event.is_set():
                return
            try:
                success, favicon_url = self.download_favicon(domain)
            except Exception as e:
                self.log_message(self.t("task_error", domain=domain, error=e))
                success, favicon_url = False, None

            results[index] = (domain, success, favicon_url)

            with lock:
                counter["done"] += 1
                current = counter["done"]
            if progress_callback:
                progress_callback(current, total_domains)

            # 添加短暂延迟以避免请求过于频繁
            time.sleep(0.5)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(handle, i, domain) for i, domain in enumerate(domains)]
            # 用户点停止后，把还没开始的任务取消掉
            for future in futures:
                if self.stop_event.is_set():
                    future.cancel()
                future.result()

        successful_downloads = []
        failed_downloads = []
        for item in results:
            if item is None:
                continue
            domain, success, favicon_url = item
            if success:
                successful_downloads.append((domain, favicon_url))
            else:
                failed_downloads.append(domain)

        # 导出结果
        self.export_results(successful_downloads, failed_downloads)

        self.log_message(self.t("done"))
        self.log_message(self.t("ok_count", n=len(successful_downloads)))
        self.log_message(self.t("fail_count", n=len(failed_downloads)))
        if self.stop_event.is_set():
            self.log_message(self.t("stopped_note"))

        return successful_downloads, failed_downloads

    def export_results(self, successful_downloads, failed_downloads):
        """导出成功和失败的结果到txt文件"""
        # 导出成功的结果
        with open("successful_downloads.txt", "w", encoding="utf-8") as f:
            f.write(self.t("csv_header") + "\n")
            for domain, url in successful_downloads:
                f.write(f"{domain},{url}\n")

        # 导出失败的结果
        with open("failed_downloads.txt", "w", encoding="utf-8") as f:
            for domain in failed_downloads:
                f.write(f"{domain}\n")

        self.log_message(self.t("exported"))
