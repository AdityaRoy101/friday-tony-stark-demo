"""
System tools — time, environment info, shell commands, etc.
"""

import datetime
import os
import platform
import shutil
import socket


def register(mcp):

    @mcp.tool()
    def get_current_time() -> str:
        """Return the local date and time in ISO 8601 format."""
        return datetime.datetime.now().astimezone().isoformat()

    @mcp.tool()
    def get_system_info() -> dict:
        """Return basic information about the host system."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        }

    @mcp.tool()
    def get_system_snapshot() -> dict:
        """
        Return a concise local system snapshot without running shell commands.
        Use this when the user asks about this computer, runtime, disk, or host.
        """
        disk = shutil.disk_usage(os.getcwd())
        return {
            "hostname": socket.gethostname(),
            "cwd": os.getcwd(),
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "local_time": datetime.datetime.now().astimezone().isoformat(),
        }
