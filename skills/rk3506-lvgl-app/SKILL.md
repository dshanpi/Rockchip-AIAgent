---
name: rk3506-lvgl-app
description: Use this skill when supporting, building, running, debugging, or modifying the RK3506 LVGL application in this SDK. It fixes the workflow around app/lvgl_demo, Buildroot package lvgl_demo, /usr/bin/rk_demo, RKADK/DRM display backends, serial-agent based board checks, and repacking/flashing the rootfs after LVGL changes.
---

# RK3506 LVGL App

Use this SDK root as the working directory. For board access, use the `rk3506-serial-agent` workflow. For reflashing after image changes, use the `rk3506-openrockcli-flash` workflow.

## Current App Layout

- LVGL app source: `app/lvgl_demo`
- Default RK3506 app: `app/lvgl_demo/rk_demo`
- Simple official-demo app: `app/lvgl_demo/lv_demo`
- Buildroot package: `buildroot/package/rockchip/lvgl_demo`
- Buildroot config: `buildroot/configs/rockchip_rk3506_defconfig`
- Built target binary: `/usr/bin/rk_demo`
- Built host target path: `buildroot/output/rockchip_rk3506/target/usr/bin/rk_demo`
- Runtime resources: `/usr/share/resource`
- Main runtime backend in current config: LVGL8 + RKADK + RGA + libdrm/libevdev

Do not use direct serial access. Use:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'ps | grep rk_demo' --wait 1.2
```

## Check Buildroot Configuration

Expected key config values in `buildroot/output/rockchip_rk3506/.config`:

```text
BR2_PACKAGE_LVGL=y
BR2_PACKAGE_LVGL_VERSION_8=y
BR2_PACKAGE_LVGL_DEMO=y
BR2_LVGL_DEMO_RK_DEMO=y
BR2_LVGL_DEMO_BACKEND_RKADK=y
BR2_PACKAGE_RKADK=y
BR2_PACKAGE_RKADK_DISPLAY=y
BR2_PACKAGE_ROCKCHIP_RGA=y
BR2_PACKAGE_LIBDRM=y
BR2_PACKAGE_LIBEVDEV=y
BR2_PACKAGE_FREETYPE=y
```

Verify:

```bash
rg -n 'BR2_PACKAGE_LVGL|BR2_PACKAGE_LV_DRIVERS|BR2_LVGL_DEMO|BR2_LVGL_DEMO_BACKEND|BR2_PACKAGE_RKADK|BR2_PACKAGE_ROCKCHIP_RGA|BR2_PACKAGE_LIBDRM|BR2_PACKAGE_LIBEVDEV|BR2_PACKAGE_FREETYPE' \
  buildroot/output/rockchip_rk3506/.config
```

## Build LVGL App

After editing `app/lvgl_demo`, rebuild the package:

```bash
./build.sh buildroot-make lvgl_demo-rebuild
```

If the package dependency state is stale:

```bash
./build.sh buildroot-make lvgl_demo-dirclean
./build.sh buildroot-make lvgl_demo
```

Check the host-side result:

```bash
ls -l buildroot/output/rockchip_rk3506/target/usr/bin/rk_demo
sed -n '1,160p' buildroot/output/rockchip_rk3506/build/lvgl_demo/install_manifest.txt
```

## Repack Rootfs And Firmware

After rebuilding the package, rebuild rootfs and firmware images before flashing:

```bash
./build.sh rootfs
./build.sh firmware
```

Then flash with the RK3506 OpenRockCLI/upgrade-tool workflow.

## Runtime Checks On Board

Check whether LVGL app and DRM nodes exist:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd \
  'ls -l /usr/bin/rk_demo /dev/dri 2>&1; ps | grep -E "rk_demo|lv_demo" | grep -v grep' \
  --wait 1.5
```

Expected successful signs:

- `/usr/bin/rk_demo` exists and is executable.
- `/dev/dri/card0` exists.
- `ps` shows `rk_demo`.

Manual restart:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd \
  'killall rk_demo 2>/dev/null; LV_DRIVERS_SET_PLANE=CURSOR rk_demo &' \
  --wait 2
```

If start scripts are present:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd \
  'find /etc/init.d -name "*lv_demo*" -maxdepth 3 -type f -print -exec sh {} start \\;' \
  --wait 2
```

## Useful Runtime Debug

Enable DRM debug for one manual run:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd \
  'killall rk_demo 2>/dev/null; LVGL_DRM_DEBUG=1 LV_DRIVERS_SET_PLANE=CURSOR rk_demo' \
  --wait 3
```

Check display/input nodes:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd \
  'ls -l /dev/dri /dev/input 2>&1; cat /proc/cmdline' \
  --wait 1.5
```

## Editing Guidance

- Prefer editing `app/lvgl_demo/rk_demo` for the production RK3506 UI.
- Use `app/lvgl_demo/lv_demo` only for minimal official LVGL demos.
- Keep LVGL version 8 unless there is a specific migration task; `rk_demo` currently rejects LVGL9 in CMake.
- Keep resources under `app/lvgl_demo/rk_demo/resource`; CMake installs them to `/usr/share/resource`.
- Keep startup assumptions compatible with `LV_DRIVERS_SET_PLANE=CURSOR`.
