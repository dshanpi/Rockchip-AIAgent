---
name: rk3506-adb-debug
description: Use this skill when debugging the RK3506 board through ADB from this SDK, including adb devices, adb shell, uploading or downloading application files, collecting logs, starting/stopping apps, and checking adbd/USB gadget state. It complements the serial-agent workflow and must not stop the RK3506 serial daemon.
---

# RK3506 ADB Debug

Use this SDK root as the working directory. ADB is for application/debug access after Linux has booted; use `rk3506-serial-agent` for boot logs, recovery, and cases where ADB is not enumerated.

Do not stop the serial daemon while using ADB.

## Host Tools

Prefer the host `adb` in `PATH`. If missing, locate SDK copies before installing anything:

```bash
command -v adb || find . -path '*adb' -type f -perm -111 | head -n 20
adb version
```

## Detect Device

Check USB and ADB state:

```bash
lsusb | sed -n '1,120p'
adb kill-server
adb start-server
adb devices -l
```

Expected ADB success is a device listed as `device`. If it is `unauthorized`, use the board UI/key workflow if available; otherwise fall back to serial.

If no ADB device appears, check the board through serial:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'ps | grep -E "adbd|usbdevice" | grep -v grep; ls -l /dev/usb-ffs/adb 2>/dev/null; cat /var/log/usbdevice.log 2>/dev/null | tail -n 80' --wait 1.5
```

## Shell

Open an interactive shell:

```bash
adb shell
```

Run one-shot commands:

```bash
adb shell uname -a
adb shell 'cat /etc/os-release 2>/dev/null || cat /etc/issue 2>/dev/null'
adb shell 'ps | head; df -h; mount | head'
```

## Upload And Download

Upload an application or test artifact:

```bash
adb push ./local-app-or-file /tmp/
adb shell 'chmod +x /tmp/local-app-or-file 2>/dev/null || true; ls -lh /tmp/local-app-or-file'
```

Download logs or generated files:

```bash
adb pull /var/log/usbdevice.log ./usbdevice.log
adb pull /tmp/remote-output ./remote-output
```

For larger app deployment tests, push to `/userdata`, `/oem`, or another writable partition after checking `df -h`.

## App Debugging

Use ADB for application iteration when the file system is writable and the app can run without reflashing:

```bash
adb shell 'ps | grep -E "rk_demo|lvgl|your_app" | grep -v grep'
adb push ./your_app /tmp/your_app
adb shell 'chmod +x /tmp/your_app && /tmp/your_app'
```

Collect kernel and system logs:

```bash
adb shell dmesg | tail -n 160
adb shell 'cat /var/log/messages 2>/dev/null | tail -n 160'
```

## Verification After Flash

After a successful OpenRockCLI flash and reboot:

```bash
adb wait-for-device
adb devices -l
adb shell uname -a
adb shell 'date; uptime'
```

If ADB never appears but serial shows the board booted, report ADB as unavailable and include the serial `ps`/`usbdevice.log` evidence.
