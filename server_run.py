# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
# server_run.py
import os


def main():
    port = os.getenv("PORT", "3011")
    workers = os.getenv("WORKERS", "1")

    cmd = [
        "granian",
        "--interface",
        "asgi",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--workers",
        workers,
        "server:app",
    ]

    # Replace current process with Granian (Rust ASGI server, project's prod server).
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
