# Rockchip-AIAgent

RK3506 development helper tools and Codex/Trae skills.

## Layout

- `tools/serial_agent/`: single-owner RK3506 serial daemon, client, terminal helpers, and agent integration examples.
- `tools/openrockcli/`: OpenRockCLI binary package for Rockchip USB scan and `update.img` flashing.
- `skills/`: RK3506 workflow skills for serial access, OpenRockCLI flashing, ADB debug, and LVGL app work.

## Notes

- `tools/openrockcli` intentionally contains only the prebuilt Linux x86_64 binary, README, license, and udev rule. OpenRockCLI source files are not included.
- Serial-agent paths in the skills point to `tools/serial_agent/...`.
- Default RK3506 serial settings are `/dev/ttyUSB0` at `1500000` baud, with `/tmp/rk3506-serial.sock` and `/tmp/rk3506-serial.log`.
