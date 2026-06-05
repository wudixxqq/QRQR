#!/usr/bin/env python3
"""
QR Monitor - 自动构建脚本
使用 PyInstaller 打包项目为独立 EXE 文件

用法:
    python build.py              # 标准打包
    python build.py --console    # 带控制台窗口（调试用）
    python build.py --clean      # 清理临时文件后打包
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "QRMonitor.spec"
LOGS_DIR = PROJECT_ROOT / "logs"


def clean_build():
    """清理之前的构建产物"""
    print("[*] Cleaning previous build artifacts...")

    for dir_path in [DIST_DIR, BUILD_DIR, LOGS_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path, ignore_errors=True)

    for pattern in ["*.spec", "*.exe"]:
        for f in PROJECT_ROOT.glob(pattern):
            if f.name != "QRMonitor.spec":
                f.unlink(missing_ok=True)

    pycache_dirs = list(PROJECT_ROOT.rglob("__pycache__"))
    for d in pycache_dirs:
        shutil.rmtree(d, ignore_errors=True)

    print("[+] Clean complete")


def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_pyinstaller():
    """安装 PyInstaller"""
    print("[*] Installing PyInstaller...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
        check=True
    )
    print("[+] PyInstaller installed")


def build_exe(console_mode: bool = False):
    """执行打包"""
    print("[*] Starting build process...")
    print(f"    Python: {sys.executable}")
    print(f"    Project: {PROJECT_ROOT}")
    print(f"    Console mode: {console_mode}")

    spec_file = SPEC_FILE

    if not spec_file.exists():
        print(f"[-] Spec file not found: {spec_file}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_file),
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--noconfirm",
    ]

    if console_mode:
        spec_content = spec_file.read_text(encoding="utf-8")
        spec_content = spec_content.replace("console=False", "console=True")
        spec_content = spec_content.replace(
            "disable_windowed_traceback=False",
            "disable_windowed_traceback=True"
        )
        temp_spec = spec_file.with_stem(spec_file.stem + "_debug")
        temp_spec.write_text(spec_content, encoding="utf-8")
        cmd[3] = str(temp_spec)
        print("[*] Building with console window (debug mode)")

    print("[*] Running PyInstaller...")
    result = subprocess.run(cmd)

    if temp_spec and temp_spec.exists():
        temp_spec.unlink()

    if result.returncode != 0:
        print(f"[-] Build failed with exit code {result.returncode}")
        sys.exit(1)

    exe_path = DIST_DIR / "QRMonitor" / "QRMonitor.exe"
    if exe_path.exists():
        print(f"[+] Build successful!")
        print(f"    Output: {exe_path}")
        print(f"    Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        # 检查 EXE 是否直接在 dist 目录下（单文件模式）
        exe_path_direct = DIST_DIR / "QRMonitor.exe"
        if exe_path_direct.exists():
            print(f"[+] Build successful!")
            print(f"    Output: {exe_path_direct}")
            print(f"    Size: {exe_path_direct.stat().st_size / 1024 / 1024:.1f} MB")
        else:
            print("[-] Build may have failed: output EXE not found")
            sys.exit(1)

    # 构建完成后将 config.yaml 复制到 dist 目录（与 EXE 同目录）
    _src_config = PROJECT_ROOT / "config.yaml"
    _dist_config = DIST_DIR / "config.yaml"
    if _src_config.exists():
        import shutil
        shutil.copy2(str(_src_config), str(_dist_config))
        print(f"[+] Config copied to: {_dist_config}")
    else:
        print("[-] Warning: config.yaml not found in project root")


def verify_build():
    """验证打包结果"""
    exe_path = DIST_DIR / "QRMonitor" / "QRMonitor.exe"
    if not exe_path.exists():
        print("[-] Verification failed: EXE not found")
        return False

    required_files = [
        "config.yaml",
    ]
    for f in required_files:
        f_path = DIST_DIR / "QRMonitor" / f
        if not f_path.exists():
            print(f"[-] Missing required file: {f}")

    file_count = len(list((DIST_DIR / "QRMonitor").rglob("*")))
    print(f"[+] Verification passed: {file_count} files in output")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="QR Monitor Build Script"
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Build with console window (debug mode)"
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Clean build artifacts before building"
    )
    parser.add_argument(
        "--install-pyinstaller", action="store_true",
        help="Install/upgrade PyInstaller first"
    )
    args = parser.parse_args()

    os.chdir(str(PROJECT_ROOT))

    if args.clean:
        clean_build()

    if args.install_pyinstaller or not check_pyinstaller():
        if not check_pyinstaller():
            print("[*] PyInstaller not found")
        install_pyinstaller()

    build_exe(args.console)
    verify_build()


if __name__ == "__main__":
    main()