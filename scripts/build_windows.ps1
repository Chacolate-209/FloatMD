# Build FloatMD green folder for Windows (MUST run on Windows).
# Produces: dist\FloatMD\FloatMD.exe + _internal\  and dist\FloatMD-windows-x64.zip
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install -e .
python -m pip install "pyinstaller>=6.0" "appdirs>=1.4"

if (Test-Path ".\dist\FloatMD") { Remove-Item -Recurse -Force ".\dist\FloatMD" }
if (Test-Path ".\build\FloatMD") { Remove-Item -Recurse -Force ".\build\FloatMD" }
if (Test-Path ".\build\floatmd") { Remove-Item -Recurse -Force ".\build\floatmd" }

python -m PyInstaller --noconfirm floatmd.spec

$AppDir = Join-Path $Root "dist\FloatMD"
$Exe = Join-Path $AppDir "FloatMD.exe"
if (-not (Test-Path $Exe)) {
    throw "Build failed: FloatMD.exe not found. Did you run this on Windows?"
}

@"
FloatMD 绿色版（Windows）
========================

【重要】请复制整个 FloatMD 文件夹，不要只拷 FloatMD.exe。
  - FloatMD.exe …… 主程序
  - _internal\  …… 运行库（必须在）
  - 启动.bat    …… 双击启动

启动：双击 启动.bat 或 FloatMD.exe

配置与笔记：
  %LOCALAPPDATA%\FloatMD\

AI 配置：打开软件后点顶栏齿轮，填写 Base URL / Model / API Key。
"@ | Set-Content -Encoding UTF8 (Join-Path $AppDir "使用说明.txt")

@"
@echo off
cd /d "%~dp0"
start "" "FloatMD.exe"
"@ | Set-Content -Encoding ASCII (Join-Path $AppDir "启动.bat")

$Zip = Join-Path $Root "dist\FloatMD-windows-x64.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path $AppDir -DestinationPath $Zip

Write-Host ""
Write-Host "======== 打包完成 ========"
Write-Host "绿色目录: $AppDir\"
Write-Host "  主程序: $Exe"
Write-Host "压缩包:   $Zip"
Write-Host "请分发整个文件夹或 zip，不要只发单个 exe。"
