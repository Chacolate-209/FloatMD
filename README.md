# FloatMD

桌面上的悬浮笔记工具：随时记、好看地读，需要时用 AI 改几行，还能截图识字。

面向 Windows（也支持从源码在 Linux 上跑）。笔记就是本地 `.md` 文件，数据在你自己电脑上。

---

## 它解决什么问题

写东西时经常要在「大编辑器 / 浏览器 / 聊天窗口」之间来回切：记一句灵感要打开一整套软件，看 Markdown 要么是裸文本要么是笨重的知识库，改两段话还要把全文贴给 AI。

FloatMD 做成一块**常驻桌面的小悬浮窗**：

- 需要就置顶，不需要就收进托盘  
- 编辑和美化预览一键切换  
- AI 只动你选中的那几行（整篇重排是单独的「排版」）  
- 截图 / 粘贴图片就能 OCR，结果插回笔记  

适合：边看文档边记要点、边写边让 AI 润色局部、随手抓屏里的字。

---

## 功能

| 能力 | 说明 |
|------|------|
| **悬浮窗** | 无边框、可拖拽缩放、置顶、系统托盘显隐 |
| **Markdown 笔记** | 本地 `.md` 存储，自动保存，弹出列表切换 / 新建 |
| **编辑模式** | 行号；点行号或拖行号可多选整行 |
| **显示模式** | 美化预览（标题 / 代码高亮 / 公式 / Mermaid 等） |
| **AI 解释** | 把选中行加入上下文，只说明、不改文件 |
| **AI 改写** | 锁定选中行范围，确认后只写回这几行 |
| **AI 排版** | 按需优化整篇 Markdown 结构（分段、标题、列表） |
| **OCR** | 画框截屏 / 粘贴 / 拖入图片 → 识别 → 插入或复制 |
| **AI 接口** | 任意 OpenAI 兼容服务（OpenAI、DeepSeek、本地 Ollama 等） |

AI **不保存长对话**，也不调用工具；密钥存在系统凭证库，不写进配置文件。

---

## 获取与启动

### 下载（Windows 推荐）

1. 打开本仓库 [Actions · Build Windows](https://github.com/Chacolate-209/FloatMD/actions)  
2. 选一次成功的运行 → 下载 Artifact **`FloatMD-windows-x64`**  
3. 解压后进入 `FloatMD` 文件夹，双击 **`启动.bat`** 或 **`FloatMD.exe`**

请保留整个文件夹（尤其是 `_internal`），不要只拷贝一个 exe。

若已有 Release，也可在 [Releases](https://github.com/Chacolate-209/FloatMD/releases) 下载安装包。

### 从源码运行

需 Python 3.10+：

```bash
git clone https://github.com/Chacolate-209/FloatMD.git
cd FloatMD
pip install -e .
python -m floatmd
```

---

## 使用方法

### 日常记笔记

1. 启动后出现悬浮窗，默认可置顶  
2. 顶栏 **写 / 阅**：写 Markdown，或切换到美化预览  
3. 点笔记名切换或新建；内容自动保存  
4. **—** 隐藏到托盘，托盘图标可再打开；**✕** 退出  

### 配置 AI

1. 点顶栏 **⚙**  
2. 填写：  
   - **Base URL**（如 `https://api.openai.com/v1`、`https://api.deepseek.com/v1`、`http://127.0.0.1:11434/v1`）  
   - **Model**（如 `gpt-4o-mini`、`deepseek-chat`）  
   - **API Key**（Ollama 可填任意非空，例如 `ollama`）  
3. 保存（更换地址时会确认一次）  

### 用 AI 辅助写作

1. 在 **写** 模式下选中若干行（可点左侧行号，或拖动行号多选）  
2. 打开 **AI** → **＋选区**（可多次加入多段上下文）  
3. 可选填一句说明，然后：  
   - **解释**：只看说明  
   - **改写**：确认后写回刚才锁定的那些行  
   - **排版**：整理整篇结构（会替换全文，请确认）  

### OCR 识图

1. 打开 **OCR**  
2. **截屏**画框，或 **粘贴** / 拖入图片  
3. 识别后 **插入**、**追加** 或 **复制**  

### 数据在哪

| | Windows | Linux |
|--|---------|--------|
| 笔记 | `%LOCALAPPDATA%\FloatMD\notes\` | `~/.local/share/floatmd/notes/` |
| 配置 | `%LOCALAPPDATA%\FloatMD\config.json` | `~/.local/share/floatmd/config.json` |

笔记是普通 Markdown，可用其他编辑器打开。API Key 不在配置文件里。

---

## 快捷键

| 快捷键 | 作用 |
|--------|------|
| `Ctrl+E` | 写 / 阅 切换 |
| `Ctrl+Shift+A` | 打开 / 关闭 AI |
| `Ctrl+Shift+O` | 打开 / 关闭 OCR |
| `Ctrl+,` | 设置 |
| `Ctrl+S` | 立即保存 |
| `Esc` | 先收起 AI/OCR；再按隐藏到托盘 |

---

## 反馈

问题与建议请开 [Issues](https://github.com/Chacolate-209/FloatMD/issues)。
