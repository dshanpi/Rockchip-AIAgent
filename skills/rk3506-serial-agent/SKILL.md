---
name: rk3506-serial-agent
description: Use this skill when working with the RK3506 board serial console in this SDK, especially when the user asks to view serial output, keep a serial monitor open with nc, send shell commands over serial, or avoid direct picocom/minicom/cat access. It fixes the workflow on tools/serial_agent with /dev/ttyUSB0 at 1500000 baud, TCP 127.0.0.1:23333, Unix socket /tmp/rk3506-serial.sock, and log file /tmp/rk3506-serial.log.
---

# RK3506 Serial Agent

Always use the repository's `tools/serial_agent` as the single owner of `/dev/ttyUSB0`.
Do not directly open the serial device with `picocom`, `minicom`, `screen`, `cat /dev/ttyUSB0`, or shell redirection while the agent is running.

## Daemon Lifetime

Keep the serial daemon running after starting it. Do not stop, kill, close, or clean up the daemon at the end of a task unless the user explicitly asks to stop the daemon.

If the daemon must be restarted to apply a code change or recover a broken state, restart it immediately with the fixed settings below and leave it running. Report that it was restarted.

Allowed stop command only when explicitly requested by the user:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock stop
```

## Fixed Settings

- Port: `/dev/ttyUSB0`
- Baudrate: `1500000`
- Unix socket: `/tmp/rk3506-serial.sock`
- TCP terminal: `127.0.0.1:23333`
- Log file: `/tmp/rk3506-serial.log`
- Agent script: `tools/serial_agent/serial_agent_daemon.py`
- Client script: `tools/serial_agent/serial_agent_client.py`

## Start Or Verify Agent

From the SDK root:

```bash
pgrep -af 'serial_agent_daemon.py' || true
ss -ltnp '( sport = :23333 )' || true
ls -l /dev/ttyUSB0
```

If no compatible agent is running, start it and keep the session alive:

```bash
python3 tools/serial_agent/serial_agent_daemon.py \
  --port /dev/ttyUSB0 \
  --baudrate 1500000 \
  --unix-sock /tmp/rk3506-serial.sock \
  --tcp-host 127.0.0.1 \
  --tcp-port 23333 \
  --log-file /tmp/rk3506-serial.log
```

If an old agent is using another socket or baudrate, stop it gracefully through its client if possible. Only kill it when it cannot be controlled and it blocks the fixed port or serial device.

After resolving a blocked or incompatible agent, start the fixed daemon again and keep it running.

## User Monitoring With nc

Tell the user to keep a persistent serial console open with:

```bash
nc 127.0.0.1 23333
```

The `nc` session can display output and accept typed commands. Closing `nc` does not stop the daemon.

If the user only wants passive logs:

```bash
tail -f /tmp/rk3506-serial.log
```

## Agent Commands

Check status:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock status
```

Tail recent output:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock tail -n 120
```

Run a shell command on the board:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'uname -a' --wait 1.2
```

Send a raw line:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock write 'reboot' --enter
```

## Validation

After starting the agent, verify both access paths:

```bash
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock status
python3 tools/serial_agent/serial_agent_client.py --sock /tmp/rk3506-serial.sock cmd 'uname -a' --wait 1.2
timeout 2s nc 127.0.0.1 23333 </dev/null | sed -n '1,80p'
```

Expected board prompt is similar to:

```text
root@rk3506-buildroot:/#
```

Do not stop the daemon after validation unless the user explicitly requested shutdown.
