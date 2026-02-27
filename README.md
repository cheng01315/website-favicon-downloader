# 网站图标下载器

一个用于批量下载网站图标（favicon）的工具，支持命令行和图形界面两种操作方式。

## 目录结构

```
网站图标下载器/
├── favicon_downloader.exe      # 命令行版本可执行文件
├── favicon_gui.exe             # 图形界面版本可执行文件
├── README.md                   # 项目说明文档
├── website_ico/                # 下载的图标文件存放目录
├── successful_downloads.txt    # 成功下载的记录文件
├── failed_downloads.txt        # 下载失败的记录文件
├── test_list.txt        		# 需要被下降的网站域名列表（一行一个）
└── src/                        # 源代码目录
    ├── favicon_core.py         # 核心下载逻辑
    ├── favicon_downloader.py   # 命令行版本主程序
    ├── favicon_gui.py          # GUI版本主程序
    ├── favicon_downloader.spec # PyInstaller配置文件
    ├── favicon_gui.spec        # GUI版本PyInstaller配置文件
    └── __pycache__/            # Python缓存文件目录
```

## 功能特点

- 支持从多个API获取网站图标（Google、faviconkit、Yandex、DuckDuckGo、Icon Horse）
- 提供命令行和图形界面两种操作方式
- 可以从文本文件批量读取域名
- 自动导出成功和失败的下载结果
- 支持多种图像格式（PNG、JPG、GIF、WEBP等）

## 使用方法

### 命令行版本 (favicon_downloader.exe)

1. 创建一个包含域名的文本文件，每行一个域名，例如：
   ```
   www.google.com
   www.github.com
   www.stackoverflow.com
   www.python.org
   ```

2. 运行可执行文件并指定域名文件路径：
   ```
   favicon_downloader.exe domains.txt
   ```

3. 程序将开始批量下载图标，下载过程中会有进度提示

### 图形界面版本 (favicon_gui.exe)

1. 双击运行 `favicon_gui.exe`
2. 点击"浏览"按钮选择域名文件
3. 点击"开始下载"按钮
4. 可以实时查看下载进度和日志信息

## 文件说明

### 可执行文件
- `favicon_downloader.exe`：命令行版本，适用于批处理和脚本
- `favicon_gui.exe`：图形界面版本，操作更直观

### 输出文件
- `website_ico/`：此文件夹存放所有下载的图标文件，每个图标以网站域名命名
- `successful_downloads.txt`：记录成功下载的网站域名和对应的图标URL
- `failed_downloads.txt`：记录下载失败的网站域名

### 源代码
- `src/`：包含所有Python源代码，用于开发和维护

## 注意事项

- 为避免请求过于频繁，程序会在每次请求之间添加短暂延迟
- 无效的图标文件（小于100字节）会被忽略
- 程序会自动创建必要的文件夹和记录文件
- 图标文件保存在 `website_ico` 文件夹中，您可以直接打开该文件夹查看下载的所有图标