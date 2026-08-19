#!/usr/bin/env python3
"""
Awesome-Janson Doctor
跨平台環境診斷腳本：支援 macOS (Apple Silicon / Intel) 與 Windows
"""
import sys
import os
import platform
import subprocess
import shutil

def check_command(cmd, name, install_mac, install_win):
    path = shutil.which(cmd)
    if path:
        print(f"✅ {name}: 已安裝 ({path})")
        return True
    else:
        print(f"❌ {name}: 未找到")
        if platform.system() == "Darwin":
            print(f"   👉 macOS 安裝指令: {install_mac}")
        else:
            print(f"   👉 Windows 安裝指令: {install_win}")
        return False

def check_python_package(pkg, name, install_name=None):
    try:
        __import__(pkg)
        print(f"✅ Python 套件 {name}: 已安裝")
        return True
    except ImportError:
        print(f"⚠️ Python 套件 {name}: 未安裝 (執行 `pip install {install_name or pkg}` 安裝)")
        return False

def check_ffmpeg_libass():
    try:
        out = subprocess.check_output(["ffmpeg", "-filters"], stderr=subprocess.STDOUT, text=True)
        if "subtitles" in out or "ass" in out:
            print("✅ FFmpeg: 具備 libass 字幕燒錄支援")
            return True
        else:
            print("⚠️ FFmpeg: 缺少 libass 支援 (建議安裝支援 libass 的版本)")
            return False
    except Exception:
        return False

def main():
    print("=" * 50)
    print("🎬 【剪神 / Awesome-Janson】環境相容性診斷")
    print(f"🖥️ 作業系統: {platform.system()} ({platform.machine()})")
    print(f"🐍 Python 版本: {platform.python_version()}")
    print("=" * 50)

    f1 = check_command("ffmpeg", "FFmpeg", "brew install ffmpeg", "winget install Gyan.FFmpeg")
    f2 = check_command("ffprobe", "FFprobe", "brew install ffmpeg", "winget install Gyan.FFmpeg")
    f3 = check_command("node", "Node.js", "brew install node", "winget install OpenJS.NodeJS")
    
    if f1:
        check_ffmpeg_libass()

    print("-" * 50)
    check_python_package("faster_whisper", "faster-whisper (本地語音辨識)", "faster-whisper")
    check_python_package("PIL", "Pillow（本地／fal B-roll 畫面）", "Pillow")

    print("=" * 50)
    print("✨ 診斷完成！只要 FFmpeg 與 Python 就緒，剪神即可直接開工。")

if __name__ == "__main__":
    main()
