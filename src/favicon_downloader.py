import os
import requests
import time
from urllib.parse import urlparse
from pathlib import Path

class FaviconDownloader:
    def __init__(self):
        self.website_ico_dir = Path("website_ico")
        self.website_ico_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 多个favicon获取API接口
        self.api_endpoints = [
            "https://www.google.com/s2/favicons?domain={}&sz=256",  # Google favicon API
            "https://api.faviconkit.com/{}/256",  # faviconkit API
            "https://favicon.yandex.net/favicon/{}/256",  # Yandex favicon API
            "https://icons.duckduckgo.com/ip3/{}.ico",  # DuckDuckGo favicon API
            "https://icon.horse/icon/{}"  # Icon Horse API
        ]
    
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
            print(f"错误：文件 {file_path} 不存在")
        except Exception as e:
            print(f"读取文件时发生错误：{e}")
        
        return domains
    
    def get_favicon_url(self, domain):
        """尝试多个API获取网站图标URL"""
        for api_url in self.api_endpoints:
            try:
                # 替换API URL中的域名
                url = api_url.format(domain)
                
                # 尝试下载图标
                response = self.session.get(url, timeout=10)
                if response.status_code == 200 and len(response.content) > 0:
                    # 检查响应是否为有效图像
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type or (content_type == '' and len(response.content) > 0):
                        # 检查是否为非常小的图像（可能是默认图标）
                        if len(response.content) < 100:  # 小于100字节可能是默认图标
                            print(f"警告: {domain} 的图标文件过小 ({len(response.content)} 字节)，可能不是有效的图标")
                            continue
                        return url, response.content
            except Exception as e:
                print(f"尝试API {api_url.format(domain)} 失败: {e}")
                continue
        
        return None, None
    
    def download_favicon(self, domain):
        """下载单个网站的图标"""
        print(f"正在下载 {domain} 的图标...")
        
        favicon_url, favicon_content = self.get_favicon_url(domain)
        
        if favicon_content:
            # 生成文件名，替换非法字符
            safe_domain = "".join(c for c in domain if c.isalnum() or c in ('.', '-')).rstrip()
            file_extension = self.get_file_extension(favicon_content)
            
            file_path = self.website_ico_dir / f"{safe_domain}{file_extension}"
            
            try:
                with open(file_path, 'wb') as f:
                    f.write(favicon_content)
                print(f"成功下载 {domain} 的图标: {file_path}")
                return True, favicon_url
            except Exception as e:
                print(f"保存图标失败 {domain}: {e}")
                return False, favicon_url
        else:
            print(f"无法获取 {domain} 的图标")
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
        elif content[:8] == b'\x00\x00\x00\x00JFIF':
            return '.jpg'
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            return '.webp'
        else:
            # 默认使用PNG
            return '.png'
    
    def process_domains_file(self, input_file):
        """处理包含域名的txt文件"""
        domains = self.read_domains_from_file(input_file)
        
        if not domains:
            print("没有找到有效的域名")
            return
        
        successful_downloads = []
        failed_downloads = []
        
        for domain in domains:
            success, favicon_url = self.download_favicon(domain)
            
            if success:
                successful_downloads.append((domain, favicon_url))
            else:
                failed_downloads.append(domain)
            
            # 添加短暂延迟以避免请求过于频繁
            time.sleep(0.5)
        
        # 导出结果
        self.export_results(successful_downloads, failed_downloads)
        
        print(f"\n下载完成！")
        print(f"成功: {len(successful_downloads)} 个")
        print(f"失败: {len(failed_downloads)} 个")
    
    def export_results(self, successful_downloads, failed_downloads):
        """导出成功和失败的结果到txt文件"""
        # 导出成功的结果
        with open("successful_downloads.txt", "w", encoding="utf-8") as f:
            f.write("域名,图标URL\n")
            for domain, url in successful_downloads:
                f.write(f"{domain},{url}\n")
        
        # 导出失败的结果
        with open("failed_downloads.txt", "w", encoding="utf-8") as f:
            for domain in failed_downloads:
                f.write(f"{domain}\n")
        
        print("结果已导出到 successful_downloads.txt 和 failed_downloads.txt")

def main():
    downloader = FaviconDownloader()
    
    # 检查是否有输入文件参数
    import sys
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("请输入包含网站域名的txt文件路径（每行一个域名）: ")
    
    if not os.path.exists(input_file):
        print(f"文件 {input_file} 不存在")
        return
    
    downloader.process_domains_file(input_file)

if __name__ == "__main__":
    main()