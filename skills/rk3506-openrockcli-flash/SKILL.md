---
name: rk3506-openrockcli-flash
description: Use this skill when flashing or upgrading the RK3506 board from this SDK, especially when the user asks to package firmware, use reboot loader to enter flashing mode, run OpenRockCLI/rockcli/Rockchip flashing, flash update.img, run rkflash.sh, or verify the board after flashing. It fixes the closed-loop workflow on build.sh firmware updateimg, serial-agent based reboot loader, tools/openrockcli/openrockcli, SDK upgrade_tool, and serial/ADB verification.
---

# RK3506 OpenRockCLI Flash

Use this SDK root as the working directory. If the current directory is not the SDK root, locate it by finding `rkflash.sh`, `rockdev/`, `tools/openrockcli/openrockcli`, and `tools/serial_agent/`.

When serial access is needed before or after flashing, use the `rk3506-serial-agent` workflow. Do not open `/dev/ttyUSB0` directly.

If the serial daemon is started for flashing or verification, leave it running after the flash completes. Do not stop it during cleanup unless the user explicitly asks to stop the daemon.

## Fixed Tools

- OpenRockCLI binary: `tools/openrockcli/openrockcli`
- Installed OpenRockCLI, if present: `openrockcli`
- SDK upgrade tool: `tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool`
- Firmware pack command: `./build.sh firmware updateimg`
- Full partition flashing script: `./rkflash.sh all`
- Firmware package: `rockdev/update.img`
- Partition image directory: `rockdev -> output/firmware`

Prefer `tools/openrockcli/openrockcli` from the SDK for Rockchip update package workflows. The `tools/openrockcli` directory in this repository is a binary package; do not expect OpenRockCLI source files to be present there.

## Closed-Loop Flash Workflow

For a normal "repackage and flash" request, use this sequence:

1. Verify or start the serial daemon through `rk3506-serial-agent`; leave it running.
2. Repack the firmware with `./build.sh firmware updateimg`.
3. Verify `rockdev/update.img` exists.
4. Try to enter flashing mode from Linux with `reboot loader` over the serial agent.
5. Poll RockUSB with `upgrade_tool LD` until a Loader or Maskrom device appears.
6. Flash `rockdev/update.img` with OpenRockCLI.
7. Verify the board rebooted through serial and, when requested or available, ADB.

Concrete commands:

```bash
./build.sh firmware updateimg
test -s rockdev/update.img && ls -lh rockdev/update.img

python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock write 'reboot loader' --enter

for i in $(seq 1 45); do
  tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool LD
  tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool LD | grep -Eq 'Mode=(Loader|Maskrom)|connected\([1-9]' && break
  sleep 1
done
```

If `reboot loader` succeeds, continue with the preferred OpenRockCLI command below.

If `reboot loader` does not enumerate RockUSB, inspect `/tmp/rk3506-serial.log` before trying other recovery paths:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock tail -n 160
rg -n 'reboot loader|Unable to handle|PC is at|Kernel panic|rfkill|wakeup_source' /tmp/rk3506-serial.log | tail -n 80
```

Known failure observed on this board: `reboot loader` reaches shutdown, unloads `rfkill_rk`, then panics at `wakeup_source_remove` from `rfkill_wlan_remove`; RockUSB never appears. Report that exact failure and do not claim flashing mode was reached. A physical reset or a kernel fix may be required before retrying.

Only use UART BREAK + SysRq `b` as a recovery attempt when the board is responsive enough and the user accepts a hard reboot:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock break --duration 0.35
sleep 0.2
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock write 'b'
```

## Device Detection

Check USB and Rockchip mode before flashing:

```bash
lsusb | sed -n '1,120p'
tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool LD || true
tools/openrockcli/openrockcli scan || true
tools/openrockcli/openrockcli devices || true
```

Known RK3506 USB ID observed in this setup:

```text
2207:350f Fuzhou Rockchip Electronics
```

`upgrade_tool LD` may report `Mode=Maskrom` or `Mode=Loader`. `Loader` mode is acceptable for normal flashing.

## Check Firmware

Before flashing, verify that the package or partition images exist:

```bash
test -e rockdev/update.img && readlink -f rockdev/update.img
find rockdev -maxdepth 1 -type f -o -type l | sort
```

For full partition flashing, confirm the required images:

```bash
for f in \
  rockdev/MiniLoaderAll.bin \
  rockdev/parameter.txt \
  rockdev/uboot.img \
  rockdev/boot.img \
  rockdev/recovery.img \
  rockdev/misc.img \
  rockdev/oem.img \
  rockdev/userdata.img \
  rockdev/rootfs.img
do
  if [ -e "$f" ]; then
    printf 'OK %s -> ' "$f"
    readlink -f "$f"
  else
    printf 'MISSING %s\n' "$f"
  fi
done
```

## Preferred OpenRockCLI update.img Flash

Use this when `rockdev/update.img` exists and the user wants the OpenixCLI/OpenRockCLI style operation:

```bash
OPENROCKCLI_UPGRADE_TOOL=tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool \
  tools/openrockcli/openrockcli flash rockdev/update.img --verbose --post-action reboot
```

Useful inspection commands:

```bash
tools/openrockcli/openrockcli inspect rockdev/update.img
tools/openrockcli/openrockcli unpack rockdev/update.img /tmp/rk3506-update-unpack
```

Partition examples:

```bash
OPENROCKCLI_UPGRADE_TOOL=tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool \
  tools/openrockcli/openrockcli flash rockdev/update.img --mode partition --partitions boot,uboot,misc,recovery --verbose

OPENROCKCLI_UPGRADE_TOOL=tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool \
  tools/openrockcli/openrockcli flash rockdev/update.img --mode partition --partitions rootfs,oem,userdata --verbose
```

## SDK Full Partition Flash Fallback

Use this when the user wants the known SDK partition-image flow or when OpenRockCLI update package flashing is not appropriate:

```bash
./rkflash.sh all
```

Expected behavior:

- It writes GPT/parameter, uboot, boot, recovery, misc, oem, userdata, and rootfs.
- It resets the device at the end.
- If the board is already in Loader mode, `ul -noreset` may print `Loading loader failed,err=-1`; continue evaluating later write results.
- This RK3506 `parameter.txt` may not define a `trust` partition, so `di -trust` can print `check download item failed`; that alone is not a failed flash if the remaining images write successfully.

## Post-Flash Verification

After flashing:

```bash
tools/linux/Linux_Upgrade_Tool/Linux_Upgrade_Tool/upgrade_tool LD || true
lsusb | sed -n '1,120p'
```

If the flash command rebooted the board, Rockusb should usually disappear from `upgrade_tool LD`.

Then verify via serial agent:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock status
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'uname -a' --wait 1.2
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'cat /etc/os-release 2>/dev/null || cat /etc/issue 2>/dev/null' --wait 1.2
```

Expected successful signs include a Buildroot shell prompt and Linux identifying as `rk3506-buildroot`.

If ADB is enabled in the image, also use the `rk3506-adb-debug` workflow for `adb devices`, `adb shell`, `adb push`, and `adb pull` checks.

Leave the serial agent running after post-flash verification unless the user explicitly requested daemon shutdown.
