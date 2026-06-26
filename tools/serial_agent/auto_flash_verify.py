#!/usr/bin/env python3
"""Auto flash an RK3506 update.img via RockUSB and verify boot via serial."""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from serial_core import auto_select_serial_port, make_serial_config, SerialSession


SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_OPENROCKCLI = f"{SDK_ROOT}/tools/openrockcli/openrockcli"

# RK3506 defaults
DEFAULT_VID = "1a86"
DEFAULT_PID = "7523"
DEFAULT_BAUDRATE = 1500000
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"


def _latest_image() -> Optional[str]:
    imgs = [f"{SDK_ROOT}/rockdev/update.img"]
    imgs.extend(glob.glob(f"{SDK_ROOT}/rockdev/*.img"))
    if not imgs:
        return None
    imgs = [img for img in imgs if os.path.exists(img)]
    imgs.sort(key=os.path.getmtime, reverse=True)
    return imgs[0] if imgs else None


def _print(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_scan(openrockcli: str, use_sudo: bool) -> tuple[int, str]:
    cmd = [openrockcli, "scan"]
    if use_sudo:
        cmd.insert(0, "sudo")
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def has_rockusb(scan_output: str) -> bool:
    return bool(re.search(r"\b(Loader|Maskrom|Rockusb|RockUSB)\b|2207:", scan_output, re.I))


def send_reboot_loader(port: str, baudrate: int) -> None:
    cfg = make_serial_config(port=port, baudrate=baudrate, timeout=1.0, write_timeout=1.0)
    sess = SerialSession(cfg)
    try:
        sess.open()
        sess.write_line("reboot loader")
        time.sleep(0.4)
        _ = sess.read_until_quiet(max_sec=1.2)
    finally:
        sess.close()


def try_uboot_rockusb(port: str, baudrate: int) -> None:
    """Best-effort fallback: reboot, break autoboot, send rockusb in U-Boot."""
    cfg = make_serial_config(port=port, baudrate=baudrate, timeout=0.2, write_timeout=1.0)
    sess = SerialSession(cfg)
    try:
        sess.open()
        sess.write_line("reboot")
        # Give reboot command a moment, then spam break keys.
        time.sleep(0.8)
        for _ in range(30):
            sess.write_bytes(b"s")
            sess.write_bytes(b"\x03")  # Ctrl+C
            time.sleep(0.12)
        sess.write_line("rockusb 0 mmc 0")
        time.sleep(0.5)
    finally:
        sess.close()


def flash_image(
    openrockcli: str,
    image: str,
    use_sudo: bool,
) -> tuple[int, bool]:
    cmd = [
        openrockcli,
        "flash",
        image,
        "--verbose",
        "--post-action",
        "reboot",
    ]
    if use_sudo:
        cmd.insert(0, "sudo")

    _print("开始烧录镜像...")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert p.stdout is not None

    success_mark = False
    for line in p.stdout:
        sys.stdout.write(line)
        if re.search(r"(success|complete|finished|done|ok)", line, re.I):
            success_mark = True

    rc = p.wait()
    return rc, success_mark or rc == 0


def verify_boot(
    serial_port: str,
    baudrate: int,
    boot_timeout_sec: int,
    max_uptime_sec: int,
) -> tuple[bool, str]:
    cfg = make_serial_config(port=serial_port, baudrate=baudrate, timeout=1.0, write_timeout=1.0)
    sess = SerialSession(cfg)
    start = time.time()
    boot_log = []
    try:
        sess.open()
        # Wait for board to finish reboot.
        while time.time() - start < boot_timeout_sec:
            out = sess.read_available_text()
            if out:
                boot_log.append(out)
                if any(k in out for k in ("login:", "# ", "$ ", "Starting kernel")):
                    break
            time.sleep(0.2)

        uname_out = sess.run_command("uname -a", max_wait_sec=4.0)
        date_out = sess.run_command("date '+%F %T %Z'", max_wait_sec=4.0)
        uptime_out = sess.run_command("cat /proc/uptime", max_wait_sec=4.0)
    finally:
        sess.close()

    uptime_val = None
    m = re.search(r"(\d+(?:\.\d+)?)", uptime_out)
    if m:
        uptime_val = float(m.group(1))

    ok_uname = "Linux" in uname_out
    ok_uptime = uptime_val is not None and uptime_val <= float(max_uptime_sec)

    detail = (
        f"uname={uname_out.strip() or '(empty)'}\n"
        f"date={date_out.strip() or '(empty)'}\n"
        f"uptime={uptime_out.strip() or '(empty)'}\n"
        f"uptime_limit={max_uptime_sec}s"
    )
    return (ok_uname and ok_uptime), detail


def main() -> int:
    parser = argparse.ArgumentParser(description="RK3506 USB + 串口自动烧录并验证启动时间")
    parser.add_argument("--image", default="", help="镜像路径，默认自动选择 rockdev/update.img")
    parser.add_argument("--openrockcli", default=DEFAULT_OPENROCKCLI, help="openrockcli 可执行文件路径")
    parser.add_argument("--serial-port", default="", help="串口设备，如 /dev/ttyUSB0")
    parser.add_argument("--serial-vid", default=DEFAULT_VID, help="自动选串口 VID")
    parser.add_argument("--serial-pid", default=DEFAULT_PID, help="自动选串口 PID")
    parser.add_argument("--baudrate", type=int, default=1500000, help="串口波特率")
    parser.add_argument("--scan-timeout-sec", type=int, default=45, help="等待 RockUSB 超时秒数")
    parser.add_argument("--boot-timeout-sec", type=int, default=120, help="启动验证超时秒数")
    parser.add_argument("--max-uptime-sec", type=int, default=300, help="判定为刚启动的最大 uptime 秒数")
    parser.add_argument("--no-sudo", action="store_true", help="不使用 sudo")
    args = parser.parse_args()

    use_sudo = not args.no_sudo
    image = args.image or _latest_image()
    if not image:
        _print("未找到镜像，请先执行 ./build.sh firmware updateimg 产出 rockdev/update.img")
        return 2
    if not os.path.exists(image):
        _print(f"镜像不存在: {image}")
        return 2
    if not os.path.exists(args.openrockcli):
        _print(f"openrockcli 不存在: {args.openrockcli}")
        return 2

    serial_port = args.serial_port
    if not serial_port:
        serial_port = auto_select_serial_port(vid=args.serial_vid, pid=args.serial_pid)

    _print(f"镜像: {image}")
    _print(f"串口: {serial_port}@{args.baudrate}")
    _print("检查是否已在 RockUSB Loader/Maskrom...")

    rc, out = run_scan(args.openrockcli, use_sudo=use_sudo)
    if rc == 0 and has_rockusb(out):
        _print("已检测到 RockUSB。")
    else:
        _print("未检测到 RockUSB，尝试通过串口发送 reboot loader...")
        send_reboot_loader(serial_port, args.baudrate)

        deadline = time.time() + args.scan_timeout_sec
        while time.time() < deadline:
            rc, out = run_scan(args.openrockcli, use_sudo=use_sudo)
            if rc == 0 and has_rockusb(out):
                _print("设备已进入 RockUSB。")
                break
            time.sleep(1.0)
        else:
            _print("reboot loader 未生效，尝试自动打断 U-Boot 并发送 rockusb...")
            try_uboot_rockusb(serial_port, args.baudrate)

            deadline = time.time() + args.scan_timeout_sec
            while time.time() < deadline:
                rc, out = run_scan(args.openrockcli, use_sudo=use_sudo)
                if rc == 0 and has_rockusb(out):
                    _print("设备已通过 U-Boot rockusb 进入 RockUSB。")
                    break
                time.sleep(1.0)
            else:
                _print("等待 RockUSB 超时。请手动进入 Loader/Maskrom 后重试。")
                return 3

    flash_rc, flash_ok = flash_image(
        openrockcli=args.openrockcli,
        image=image,
        use_sudo=use_sudo,
    )
    if flash_rc != 0 or not flash_ok:
        _print(f"烧录失败: rc={flash_rc}, success_mark={flash_ok}")
        return 4

    _print("烧录完成，开始串口启动验证（uname/date/uptime）...")
    ok, detail = verify_boot(
        serial_port=serial_port,
        baudrate=args.baudrate,
        boot_timeout_sec=args.boot_timeout_sec,
        max_uptime_sec=args.max_uptime_sec,
    )
    _print(detail)
    if not ok:
        _print("启动验证失败：未满足 uname 或 uptime 条件")
        return 5

    _print("验证通过：系统可启动，且 uptime 在阈值内，判定为本次烧录生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
