@echo off
chcp 65001 >nul
echo ========================================
echo   月亮棋 MoonChess EXE 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] 安装 PyInstaller...
    pip install pyinstaller
) else (
    echo [1/3] PyInstaller 已安装
)

REM 安装依赖
echo [2/3] 安装项目依赖...
pip install -r "%~dp0requirements.txt"

REM 打包
echo [3/3] 开始打包...
pyinstaller --clean --noconfirm "%~dp0MoonChess.spec"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   打包成功！
    echo   EXE 文件: dist\MoonChess.exe
    echo ========================================
    echo.
    echo 将 MoonChess.exe 发送给朋友即可联机对战。
    echo 注意：双方需能访问同一中继服务器。
    echo 默认地址: wss://moon-chess-relay.onrender.com
    echo 可通过环境变量 MOON_CHESS_RELAY 修改，
    echo 或在游戏内联机大厅点击服务器地址修改。
) else (
    echo.
    echo 打包失败，请检查上方错误信息。
)

pause
