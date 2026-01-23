# Code Interpreter Worker - 完整功能清单

> 最后更新: 2026-01-23

本文档列出 Worker 容器支持的所有功能、库和工具。

---

## 目录

- [运行时环境](#运行时环境)
- [科学计算](#科学计算)
- [数据可视化](#数据可视化)
- [图像处理](#图像处理)
- [视频处理](#视频处理)
- [音频处理](#音频处理)
- [文档处理](#文档处理)
- [文本处理与NLP](#文本处理与nlp)
- [日期与时间](#日期与时间)
- [网络请求](#网络请求)
- [数据格式解析](#数据格式解析)
- [压缩与归档](#压缩与归档)
- [加密与编码](#加密与编码)
- [数据验证与转换](#数据验证与转换)
- [数据库](#数据库)
- [数学与金融](#数学与金融)
- [地理位置](#地理位置)
- [浏览器自动化](#浏览器自动化)
- [实用工具](#实用工具)
- [系统工具](#系统工具)
- [Node.js 环境](#nodejs-环境)

---

## 运行时环境

| 环境 | 版本 | 说明 |
|------|------|------|
| Python | 3.12.12 | 主执行环境 |
| Node.js | 18 LTS | JavaScript 执行环境 |
| Jupyter Kernel | ipykernel 6.29.5 | 有状态代码执行 |

---

## 科学计算

| 库 | 版本 | 功能 | 示例用途 |
|----|------|------|----------|
| numpy | 2.2.6 | 数值计算 | 数组运算、线性代数、FFT |
| pandas | 2.2.3 | 数据分析 | DataFrame、数据清洗、统计 |
| scipy | 1.15.3 | 科学计算 | 优化、插值、信号处理、稀疏矩阵 |
| sympy | 1.13.3 | 符号计算 | 代数求解、微积分、方程求解 |
| scikit-learn | 1.6.1 | 机器学习 | 分类、回归、聚类、降维 |
| statsmodels | 0.14.4 | 统计建模 | 回归分析、时间序列、假设检验 |
| networkx | 3.4.2 | 图论分析 | 图算法、网络分析、路径查找 |

---

## 数据可视化

| 库 | 版本 | 功能 | 输出格式 |
|----|------|------|----------|
| matplotlib | 3.10.3 | 基础绑图 | PNG, SVG, PDF |
| seaborn | 0.13.2 | 统计可视化 | PNG, SVG |
| plotly | 6.1.2 | 交互式图表 | HTML, PNG (via kaleido) |
| pyecharts | 2.0.8 | ECharts 封装 | HTML, PNG |
| kaleido | 0.2.1 | Plotly 静态导出 | PNG, SVG, PDF |
| wordcloud | 1.9.4 | 词云生成 | PNG |

---

## 图像处理

| 库/工具 | 版本 | 功能 | 支持格式 |
|---------|------|------|----------|
| pillow | 11.1.0 | 图像处理 | PNG, JPEG, GIF, BMP, TIFF, WebP |
| opencv-python-headless | 4.11.0 | 计算机视觉 | 大多数图像/视频格式 |
| scikit-image | 0.25.2 | 图像算法 | 同 PIL |
| imageio | 2.37.0 | 图像/视频 I/O | PNG, JPEG, GIF, MP4, WebM |
| cairosvg | 2.7.1 | SVG 渲染 | SVG → PNG/PDF |
| svgwrite | 1.4.3 | SVG 创建 | SVG |
| wand | 0.6.13 | ImageMagick 绑定 | 200+ 格式 |
| rawpy | 0.25.1 | RAW 图像处理 | CR2, NEF, ARW, DNG 等 |
| qrcode | 8.2 | 二维码生成 | PNG, SVG |
| python-barcode | 0.15.1 | 条形码生成 | PNG, SVG |
| pyzbar | 0.1.9 | 条形码/二维码识别 | 从图像读取 |
| colorthief | 0.2.1 | 主色提取 | 从图像提取颜色 |
| exifread | 3.1.0 | EXIF 读取 | JPEG, TIFF |
| piexif | 1.1.3 | EXIF 编辑 | JPEG, TIFF |

### 系统级图像工具

| 工具 | 功能 |
|------|------|
| ImageMagick | 图像转换、处理、格式转换 |
| libraw | RAW 图像解码 |

---

## 视频处理

| 库/工具 | 版本 | 功能 |
|---------|------|------|
| moviepy | 2.2.1 | 视频编辑 (剪切、合并、特效、字幕) |
| ffmpeg-python | 0.2.0 | FFmpeg Python 封装 |
| av (PyAV) | 16.1.0 | FFmpeg/libav 底层绑定 |
| vidgear | 0.3.3 | 视频处理工具包 |
| imageio[ffmpeg] | 2.37.0 | 视频 I/O |

### 系统级视频工具

| 工具 | 功能 |
|------|------|
| FFmpeg | 视频编解码、转换、流处理 |
| libavcodec-extra | 额外编解码器支持 |

### 支持的视频格式

MP4, AVI, MKV, MOV, WebM, FLV, GIF (动图), 以及 FFmpeg 支持的所有格式。

---

## 音频处理

| 库 | 版本 | 功能 |
|----|------|------|
| pydub | 0.25.1 | 音频操作 (剪切、合并、格式转换) |
| librosa | 0.11.0 | 音频分析 (频谱、节拍检测、特征提取) |
| soundfile | 0.13.1 | 音频文件 I/O |
| audioread | 3.0.1 | 音频文件读取 |
| mutagen | 1.47.0 | 音频元数据读写 |
| tinytag | 2.0.0 | 音频元数据 (轻量) |
| pedalboard | 0.9.18 | 音频效果 (Spotify 开源) |
| noisereduce | 3.0.3 | 噪声降低 |

### 系统级音频工具

| 工具 | 功能 |
|------|------|
| FFmpeg | 音频编解码、转换 |
| libsndfile | 音频文件读写 |

### 支持的音频格式

MP3, WAV, FLAC, OGG, AAC, M4A, WMA, AIFF, 以及 FFmpeg 支持的所有格式。

---

## 文档处理

### Office 文档

| 库/工具 | 版本 | 功能 | 格式 |
|---------|------|------|------|
| python-docx | 1.1.2 | Word 文档读写 | .docx |
| openpyxl | 3.1.5 | Excel 文档读写 | .xlsx |
| xlrd | 2.0.1 | Excel 读取 (旧版) | .xls |
| xlsxwriter | 3.2.5 | Excel 写入 (高级格式) | .xlsx |
| python-pptx | 1.0.2 | PowerPoint 读写 | .pptx |
| LibreOffice | - | 文档转换、公式计算 | docx, xlsx, pptx, odt, ods, odp |

### PDF 文档

| 库/工具 | 版本 | 功能 |
|---------|------|------|
| PyPDF2 | 3.0.1 | PDF 基础操作 (合并、分割、旋转) |
| pdfplumber | 0.11.6 | PDF 文本/表格提取 |
| pymupdf (fitz) | 1.25.5 | PDF 渲染、高级操作 |
| poppler-utils | - | pdftotext, pdftoppm, pdfimages |
| qpdf | - | PDF 合并、分割、线性化 |
| Ghostscript | - | PDF/PostScript 处理 |

### OCR 文字识别

| 工具 | 支持语言 |
|------|----------|
| tesseract-ocr | 英文 (eng), 简体中文 (chi_sim) |

### 文档转换

| 工具 | 功能 |
|------|------|
| pandoc | Markdown ↔ Word/HTML/LaTeX/PDF 等格式互转 |
| LibreOffice | Office 文档 ↔ PDF 互转 |

### Node.js 文档库

| 库 | 功能 |
|----|------|
| docx | Word 文档创建 (JavaScript) |
| pptxgenjs | PowerPoint 创建 (JavaScript) |

---

## 文本处理与NLP

| 库 | 版本 | 功能 |
|----|------|------|
| jieba | 0.42.1 | 中文分词 |
| pypinyin | 0.54.0 | 汉字转拼音 |
| chardet | 5.2.0 | 编码检测 |
| python-Levenshtein | 0.27.1 | 字符串相似度 (编辑距离) |
| thefuzz | 0.22.1 | 模糊字符串匹配 |
| faker | 37.3.0 | 假数据生成 (姓名、地址、电话等) |
| ftfy | 6.3.1 | 修复文本编码问题 |
| emoji | 2.14.1 | Emoji 处理 |
| regex | 2024.11.6 | 高级正则表达式 |
| unidecode | 1.3.8 | Unicode 转 ASCII |
| markdown | 3.8 | Markdown 解析 |

---

## 日期与时间

| 库 | 版本 | 功能 |
|----|------|------|
| python-dateutil | 2.9.0 | 日期解析、相对时间 |
| arrow | 1.3.0 | 友好的日期时间库 |
| pendulum | 3.1.0 | 更好的日期时间处理 |
| pytz | 2025.2 | 时区处理 |
| lunarcalendar | 0.0.9 | 农历转换 |
| croniter | 6.0.0 | Cron 表达式解析 |

---

## 网络请求

| 库 | 版本 | 功能 |
|----|------|------|
| requests | 2.32.3 | HTTP 请求 (同步) |
| httpx | 0.28.1 | HTTP 请求 (同步/异步) |
| urllib3 | 2.4.0 | HTTP 底层库 |
| aiohttp | 3.12.7 | 异步 HTTP 客户端 |

> **注意**: Worker 运行在隔离网络中，默认无法访问外部互联网。

---

## 数据格式解析

| 库 | 版本 | 格式 |
|----|------|------|
| orjson | 3.10.18 | JSON (高性能) |
| pyyaml | 6.0.2 | YAML |
| toml | 0.10.2 | TOML |
| xmltodict | 0.14.2 | XML → dict |
| lxml | 5.4.0 | XML/HTML (高性能) |
| beautifulsoup4 | 4.13.4 | HTML 解析 |
| html5lib | 1.1 | HTML5 解析 |
| defusedxml | 0.7.1 | 安全 XML 解析 |
| csv23 | 0.1.6 | CSV 工具 |
| tabulate | 0.9.0 | 表格格式化输出 |

---

## 压缩与归档

| 库 | 版本 | 格式 |
|----|------|------|
| py7zr | 0.22.0 | 7z 压缩/解压 |
| rarfile | 4.2 | RAR 解压 (只读) |
| (内置) zipfile | - | ZIP 压缩/解压 |
| (内置) tarfile | - | TAR/GZ/BZ2 压缩/解压 |
| (内置) gzip | - | GZ 压缩/解压 |

---

## 加密与编码

| 库 | 版本 | 功能 |
|----|------|------|
| cryptography | 45.0.4 | 加密算法 (AES, RSA, 哈希等) |
| pyjwt | 2.10.1 | JWT 编码/解码 |
| hashids | 1.3.1 | Hashids 编码 |
| base58 | 2.1.1 | Base58 编码 |
| (内置) hashlib | - | MD5, SHA 哈希 |
| (内置) base64 | - | Base64 编码 |

---

## 数据验证与转换

| 库 | 版本 | 功能 |
|----|------|------|
| phonenumbers | 9.0.2 | 电话号码解析/验证 |
| validators | 0.34.0 | URL/Email/IP 验证 |
| humanize | 4.12.3 | 人性化数字 (1000 → "1K") |
| pint | 0.24.4 | 物理单位转换 |
| python-slugify | 8.0.4 | Slug 生成 |
| python-magic | 0.4.27 | 文件类型检测 (MIME) |

---

## 数据库

| 库 | 版本 | 功能 |
|----|------|------|
| sqlalchemy | 2.0.41 | SQL 工具包/ORM |
| (内置) sqlite3 | - | SQLite 数据库 |

> **注意**: 支持在沙箱内创建 SQLite 数据库文件进行数据存储和查询。

---

## 数学与金融

| 库 | 版本 | 功能 |
|----|------|------|
| mpmath | 1.3.0 | 任意精度数学 |
| py-money | 0.5.0 | 货币处理 |
| akshare | 1.16.89 | 中国金融数据接口 |

---

## 地理位置

| 库 | 版本 | 功能 |
|----|------|------|
| geopy | 2.4.1 | 地理编码 (地址 ↔ 坐标) |

---

## 浏览器自动化

| 库/工具 | 版本 | 功能 |
|---------|------|------|
| playwright | 1.52.0 | 浏览器自动化 |
| Chromium | (bundled) | 无头浏览器 |

### 功能

- 网页截图
- PDF 生成
- 网页测试
- 表单自动填充
- JavaScript 执行
- 网络请求拦截

---

## 实用工具

| 库 | 版本 | 功能 |
|----|------|------|
| tqdm | 4.67.1 | 进度条 |
| rich | 14.0.0 | 终端格式化输出 |
| more-itertools | 10.7.0 | 扩展迭代工具 |
| toolz | 1.0.0 | 函数式编程工具 |
| attrs | 25.3.0 | 类工具 |
| boltons | 24.1.0 | Python 工具集合 |
| cachetools | 6.0.0 | 缓存工具 |
| retry | 0.9.2 | 重试装饰器 |
| tenacity | 9.1.2 | 重试库 |
| shortuuid | 1.0.13 | 短 UUID |
| nanoid | 2.0.0 | Nano ID |
| loguru | 0.7.3 | 日志记录 |

---

## 系统工具

| 工具 | 功能 |
|------|------|
| FFmpeg | 音视频处理 |
| ImageMagick | 图像处理 |
| LibreOffice | 文档转换 |
| Pandoc | 文档格式转换 |
| Tesseract OCR | 文字识别 |
| Poppler | PDF 工具集 |
| Ghostscript | PDF/PostScript 处理 |
| qpdf | PDF 操作 |

---

## Node.js 环境

### 运行时

| 组件 | 版本 |
|------|------|
| Node.js | 18 LTS |
| npm | (bundled) |

### 全局安装的包

| 包 | 功能 |
|----|------|
| docx | Word 文档创建 |
| pptxgenjs | PowerPoint 创建 |
| typescript | TypeScript 编译器 |
| ts-node | TypeScript 直接执行 |

### 使用方式

```python
import subprocess

# 执行 Node.js 脚本
result = subprocess.run(['node', '-e', 'console.log("Hello from Node.js")'], capture_output=True, text=True)
print(result.stdout)

# 执行 TypeScript
result = subprocess.run(['ts-node', '-e', 'console.log("Hello from TypeScript")'], capture_output=True, text=True)
print(result.stdout)
```

---

## 资源限制

| 资源 | 默认值 |
|------|--------|
| CPU | 1.5 核 |
| 内存 | 1536 MB |
| 磁盘 | 500 MB |
| 执行超时 | 15 秒 |
| 网络 | 隔离 (无外网访问) |

---

## 字体支持

| 字体 | 用途 |
|------|------|
| SimHei (黑体) | 中文显示 |
| Liberation 字体族 | 西文显示 |
| fonts-liberation | LibreOffice 默认字体 |

---

## 版本信息

- **文档版本**: 1.0.0
- **Worker 镜像**: code-interpreter-worker:latest
- **基础镜像**: python:3.12.12-slim-bookworm
