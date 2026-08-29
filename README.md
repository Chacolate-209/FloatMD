# FloatMD

轻量桌面悬浮 Markdown 笔记（Python · PySide6 · Windows 优先）。

设计文档见 [`DESIGN.md`](DESIGN.md)。

## 开发运行

```bash
cd /home/FloatMD
python3 -m pip install -e .
python3 -m floatmd
```

Windows：

```powershell
cd \path\to\FloatMD
python -m pip install -e .
python -m floatmd
```

## AI 配置（URL / Model / Key）

### 界面配置（推荐）

1. 顶栏点 **⚙**，或 AI 面板里的 **⚙**
2. 填写：
   - **Base URL**：OpenAI 兼容地址，例如  
     - OpenAI：`https://api.openai.com/v1`  
     - DeepSeek：`https://api.deepseek.com/v1`  
     - 本地 Ollama：`http://127.0.0.1:11434/v1`
   - **Model**：如 `gpt-4o-mini`、`deepseek-chat`、`llama3.2`
   - **API Key**：Bearer Token（Ollama 可填任意非空，如 `ollama`）
3. 勾选「保存到系统钥匙串」→ Key 进 OS 凭证库；不勾选则仅本次进程有效
4. 保存。更换 Base URL 时会二次确认

### 落盘位置

| 项 | Linux | Windows |
|----|-------|---------|
| 配置 JSON | `~/.local/share/floatmd/config.json` | `%LOCALAPPDATA%\FloatMD\config.json` |
| 笔记目录 | `~/.local/share/floatmd/notes/` | `%LOCALAPPDATA%\FloatMD\notes\` |
| API Key | 钥匙串 / 会话内存（**不写进 JSON**） | Credential Manager / 会话 |

`config.json` 里只有 `ai.base_url` / `ai.model` 等，**没有**密钥。

### AI 操作提醒

| 按钮 | 行为 |
|------|------|
| ＋选区 | 把当前选中行加入上下文（可多段） |
| 解释 | 只出说明，不改笔记 |
| 改写 | 锁定 `Lx–Ly`，确认后只写回这几行 |
| 排版 | 整篇格式优化（唯一全量替换） |

选行：点行号 / 行号栏拖动 / Shift+点行号 / 正文拖选。

## 打包 Windows `.exe`（推荐：GitHub Actions）

当前开发机如果是 Linux，**无法直接交叉编译出可用的 Windows exe**（Qt/WebEngine 不行）。  
已提供 GitHub Actions：在 GitHub 的 **Windows 虚拟机**上自动打包。

### 步骤

1. 把本项目推到 GitHub 仓库  
2. 打开仓库 → **Actions** → **Build Windows** → **Run workflow**  
3. 跑完后在该次运行页面下载 Artifact：`FloatMD-windows-x64`  
4. 解压得到：

```
FloatMD\
  FloatMD.exe      ← Windows 主程序
  启动.bat
  使用说明.txt
  _internal\       ← 必须保留，不要只拷 exe
```

打 `v*` 标签（如 `v0.1.0`）时，还会自动挂到 Release。

> 体积大约几百 MB～1GB，下载要等一会儿。

### 本机 Windows 打包（可选）

在 Windows 上安装 Python 3.11+ 后：

```powershell
.\scripts\build_windows.ps1
# → dist\FloatMD\FloatMD.exe
# → dist\FloatMD-windows-x64.zip
```

### Linux 绿色包（仅 Linux 可用）

```bash
bash scripts/build.sh
```

Linux 产物没有 `.exe` 后缀是正常的，且 **不能** 在 Windows 运行。

### 打包注意

- 默认排除 Paddle（体积太大）；OCR 用 RapidOCR
- 配置写在 `%LOCALAPPDATA%\FloatMD\`，与绿色包路径无关

## 测试

```bash
python3 -m pytest tests/ -q
```

## 当前状态

- [x] 悬浮窗 / 托盘 / 笔记 / 编辑·预览
- [x] AI：解释 / 局部改写（行快照写回）/ 整篇排版
- [x] OCR：画框 / 粘贴 / 拖入
- [x] 浅色主题 + CJK 字体
- [x] PyInstaller 绿色目录脚本
