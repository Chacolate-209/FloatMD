#!/usr/bin/env bash
# Build FloatMD green folder (onedir) with PyInstaller — Linux.
# Output is a FOLDER you must copy as a whole (not a single file).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install -e ".[dev]" -q 2>/dev/null || python3 -m pip install -e . -q
python3 -m pip install -q 'pyinstaller>=6.0' 'appdirs>=1.4'

rm -rf build/floatmd build/FloatMD dist/FloatMD
python3 -m PyInstaller --noconfirm floatmd.spec

APP_DIR="$ROOT/dist/FloatMD"
if [[ ! -x "$APP_DIR/FloatMD" ]]; then
  echo "ERROR: missing $APP_DIR/FloatMD" >&2
  exit 1
fi

# Friendly launcher + readme inside the green folder
cat > "$APP_DIR/启动.sh" <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:---no-sandbox --disable-gpu}"
exec "$DIR/FloatMD" "$@"
EOF
chmod +x "$APP_DIR/启动.sh" "$APP_DIR/FloatMD"

cat > "$APP_DIR/使用说明.txt" <<'EOF'
FloatMD 绿色版（Linux）
========================

【重要】请复制整个 FloatMD 文件夹，不要只拷里面的「FloatMD」单个文件。
  - FloatMD      …… 主程序（Linux 可执行文件，没有 .exe 后缀是正常的）
  - _internal/   …… 运行库（必须和主程序在同一目录）
  - 启动.sh      …… 双击/终端启动用

启动：
  ./启动.sh
  或
  ./FloatMD

配置与笔记（首次运行后自动创建）：
  ~/.local/share/floatmd/

本包仅适用于 Linux x86_64。Windows 请用 scripts/build_windows.ps1 在 Windows 上打包，
会得到 FloatMD.exe。
EOF

# Archive the whole folder for distribution
ARCHIVE=""
rm -f "$ROOT/dist/FloatMD-linux-x64.zip" "$ROOT/dist/FloatMD-linux-x64.tar.gz"
if command -v zip >/dev/null 2>&1; then
  ( cd "$ROOT/dist" && zip -qr "FloatMD-linux-x64.zip" FloatMD )
  ARCHIVE="$ROOT/dist/FloatMD-linux-x64.zip"
else
  ( cd "$ROOT/dist" && tar -czf "FloatMD-linux-x64.tar.gz" FloatMD )
  ARCHIVE="$ROOT/dist/FloatMD-linux-x64.tar.gz"
fi

echo ""
echo "======== 打包完成 ========"
echo "绿色目录: $APP_DIR/"
echo "  主程序: $APP_DIR/FloatMD   (Linux 无 .exe 后缀是正常的)"
echo "  依赖库: $APP_DIR/_internal/  ← 必须一起带走"
echo "  启动:   $APP_DIR/启动.sh"
echo "压缩包:   $ARCHIVE"
echo "请分发整个文件夹或压缩包，不要只发单个 FloatMD 文件。"
echo "Windows 用户请到 Windows 上运行 scripts/build_windows.ps1 生成 FloatMD.exe"
du -sh "$APP_DIR" "$ARCHIVE"
