#!/bin/sh
set -eu

rm -f /tmp/.X99-lock || true
Xvfb :99 -screen 0 1440x900x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 &
for i in $(seq 1 50); do
  [ -S /tmp/.X11-unix/X99 ] && break
  sleep 0.1
done
fluxbox -display :99 >/tmp/fluxbox.log 2>&1 &
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw -xkb -quiet >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/novnc.log 2>&1 &

exec uvicorn app.main:app --host 0.0.0.0 --port 8090
