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
        "app.main:app",
    ]

    # Replace current process with Granian (Rust ASGI server, project's prod server).
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
