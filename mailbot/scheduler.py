"""Sistem zamanlayıcısı — PC kapalı/uykuda olsa bile planlanan saatte çalışır.

macOS: launchd (uykudan uyanınca kaçırılan görev çalışır)
Linux: at
Windows: schtasks (Task Scheduler)
"""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import ROOT_DIR


def _schedule_darwin(target: datetime, python_path: str) -> bool:
    """macOS: launchd ile planla. Uykudan uyanınca kaçırılan görev çalışır."""
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)

    label = "com.mailbot.scheduled"
    plist_path = launch_agents / f"{label}.plist"

    # Wrapper script: send-scheduled çalıştır, sonra plist'i kaldır
    wrapper = ROOT_DIR / "mailbot_scheduled.sh"
    wrapper.write_text(
        f"""#!/bin/bash
cd "{ROOT_DIR}"
"{python_path}" -m mailbot send-scheduled
launchctl unload "{plist_path}" 2>/dev/null
rm -f "{plist_path}"
""",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{wrapper}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{ROOT_DIR}</string>
    <key>StandardOutPath</key>
    <string>{ROOT_DIR / "scheduled_send.log"}</string>
    <key>StandardErrorPath</key>
    <string>{ROOT_DIR / "scheduled_send.log"}</string>
    <key>RunAtLoad</key>
    <false/>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Month</key>
        <integer>{target.month}</integer>
        <key>Day</key>
        <integer>{target.day}</integer>
        <key>Hour</key>
        <integer>{target.hour}</integer>
        <key>Minute</key>
        <integer>{target.minute}</integer>
    </dict>
</dict>
</plist>
"""
    plist_path.write_text(plist_content, encoding="utf-8")

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _schedule_windows(target: datetime, python_path: str) -> bool:
    """Windows: Task Scheduler ile planla (schtasks). Wrapper .bat dosyası kullanır."""
    task_name = "MailBotScheduled"
    date_str = target.strftime("%d/%m/%Y")
    time_str = target.strftime("%H:%M")

    # Wrapper batch: cd, çalıştır, görevi sil
    bat_path = ROOT_DIR / "mailbot_scheduled.bat"
    bat_path.write_text(
        f'@echo off\n'
        f'cd /d "{ROOT_DIR}"\n'
        f'"{python_path}" -m mailbot send-scheduled\n'
        f'schtasks /Delete /TN {task_name} /F 2>nul\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN", task_name,
            "/TR", f'"{bat_path}"',
            "/SC", "ONCE",
            "/ST", time_str,
            "/SD", date_str,
            "/F",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _schedule_linux(target: datetime, python_path: str) -> bool:
    """Linux: at komutu ile planla."""
    # at format: HH:MM MMDDYY veya HH:MM
    at_time = target.strftime("%H:%M %m%d%y")
    cmd = f'cd "{ROOT_DIR}" && "{python_path}" -m mailbot send-scheduled'
    result = subprocess.run(
        ["at", at_time],
        input=cmd,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def schedule_system(target: datetime) -> bool:
    """
    Planı sistem zamanlayıcısına kaydeder.
    PC kapatılsa/uykusa bile, belirlenen saatte (veya uykudan uyanınca) çalışır.
    Returns: True if successful
    """
    python_path = sys.executable
    system = platform.system()

    if system == "Darwin":
        return _schedule_darwin(target, python_path)
    if system == "Linux":
        return _schedule_linux(target, python_path)
    if system == "Windows":
        return _schedule_windows(target, python_path)

    return False
