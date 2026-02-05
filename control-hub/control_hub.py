import json
import os
import subprocess
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk

DEFAULT_CONFIG = {
    "compose_file": "../docker-compose.hub.yml",
    "project_name": "rfid-marathon",
    "services": [
        "rfid-postgres",
        "rfid-backend",
        "rfid-proxy",
        "udp-sender",
        "udp-listener",
    ],
}


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return DEFAULT_CONFIG.copy()
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data or {})
    return merged


def resolve_compose_path(config: dict, config_path: Path) -> str:
    compose_file = config.get("compose_file") or DEFAULT_CONFIG["compose_file"]
    compose_path = (config_path.parent / compose_file).resolve()
    return str(compose_path)


def build_compose_command(compose_path: str, project_name: str, args: list[str]) -> list[str]:
    return ["docker", "compose", "-p", project_name, "-f", compose_path, *args]


class ControlHubUI:
    def __init__(self, root: tk.Tk, config_path: Path):
        self.root = root
        self.config_path = config_path
        self.config = load_config(config_path)
        self.compose_path = resolve_compose_path(self.config, config_path)
        self.project_name = self.config.get("project_name") or DEFAULT_CONFIG["project_name"]
        self.services = self.config.get("services") or DEFAULT_CONFIG["services"]

        self.log_queues: dict[str, queue.Queue[str]] = {}
        self.log_threads: dict[str, threading.Thread] = {}
        self.log_procs: dict[str, subprocess.Popen] = {}
        self.log_text_widgets: dict[str, tk.Text] = {}
        self.service_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self._schedule_log_pump()

    def _build_ui(self) -> None:
        self.root.title("RFID Marathon Control Hub")
        self.root.geometry("1100x700")

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Control Hub", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        ttk.Button(top_frame, text="Start All", command=self.start_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Stop All", command=self.stop_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Restart All", command=self.restart_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Status", command=self.show_status).pack(side=tk.RIGHT, padx=4)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        services_frame = ttk.LabelFrame(main_frame, text="Services", padding=10)
        services_frame.pack(side=tk.LEFT, fill=tk.Y)

        for svc in self.services:
            var = tk.BooleanVar(value=False)
            self.service_vars[svc] = var
            cb = ttk.Checkbutton(
                services_frame,
                text=svc,
                variable=var,
                command=lambda s=svc: self.toggle_service(s),
            )
            cb.pack(anchor=tk.W, pady=4)

        logs_frame = ttk.LabelFrame(main_frame, text="Logs", padding=10)
        logs_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.logs_notebook = ttk.Notebook(logs_frame)
        self.logs_notebook.pack(fill=tk.BOTH, expand=True)

        for svc in self.services:
            tab = ttk.Frame(self.logs_notebook)
            self.logs_notebook.add(tab, text=svc)

            text = tk.Text(tab, wrap=tk.NONE, font=("Consolas", 10))
            text.pack(fill=tk.BOTH, expand=True)
            text.configure(state=tk.DISABLED)
            self.log_text_widgets[svc] = text

        self.status_text = tk.Text(self.root, height=6, wrap=tk.NONE, font=("Consolas", 10))
        self.status_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._append_status("Control Hub ready.\n")

    def _append_status(self, message: str) -> None:
        self.status_text.configure(state=tk.NORMAL)
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED)

    def _append_log(self, service: str, message: str) -> None:
        text = self.log_text_widgets.get(service)
        if not text:
            return
        text.configure(state=tk.NORMAL)
        text.insert(tk.END, message)
        text.see(tk.END)
        text.configure(state=tk.DISABLED)

    def _run_compose(self, args: list[str]) -> int:
        if not os.path.exists(self.compose_path):
            self._append_status(f"Compose file not found: {self.compose_path}\n")
            return 2
        cmd = build_compose_command(self.compose_path, self.project_name, args)
        self._append_status("Running: " + " ".join(cmd) + "\n")
        result = subprocess.run(cmd, check=False)
        return result.returncode

    def start_service(self, service: str) -> None:
        self._run_compose(["up", "-d", service])
        self.start_log_tail(service)
        self._append_status(f"Started {service}.\n")

    def stop_service(self, service: str) -> None:
        self._run_compose(["stop", service])
        self.stop_log_tail(service)
        self._append_status(f"Stopped {service}.\n")

    def restart_service(self, service: str) -> None:
        self._run_compose(["restart", service])
        self.start_log_tail(service)
        self._append_status(f"Restarted {service}.\n")

    def toggle_service(self, service: str) -> None:
        if self.service_vars[service].get():
            self.start_service(service)
            self.logs_notebook.select(self.services.index(service))
        else:
            self.stop_service(service)

    def start_all(self) -> None:
        for svc in self.services:
            self.service_vars[svc].set(True)
            self.start_service(svc)

    def stop_all(self) -> None:
        for svc in self.services:
            self.service_vars[svc].set(False)
            self.stop_service(svc)

    def restart_all(self) -> None:
        for svc in self.services:
            self.restart_service(svc)

    def show_status(self) -> None:
        if not os.path.exists(self.compose_path):
            self._append_status(f"Compose file not found: {self.compose_path}\n")
            return
        cmd = build_compose_command(self.compose_path, self.project_name, ["ps"])
        self._append_status("Running: " + " ".join(cmd) + "\n")
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.stdout:
            self._append_status(result.stdout + "\n")
        if result.stderr:
            self._append_status(result.stderr + "\n")

    def start_log_tail(self, service: str) -> None:
        if service in self.log_procs and self.log_procs[service].poll() is None:
            return
        if not os.path.exists(self.compose_path):
            self._append_status(f"Compose file not found: {self.compose_path}\n")
            return
        cmd = build_compose_command(
            self.compose_path,
            self.project_name,
            ["logs", "-f", "--no-color", service],
        )
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.log_procs[service] = proc
        q: queue.Queue[str] = queue.Queue()
        self.log_queues[service] = q

        def _reader() -> None:
            try:
                for line in proc.stdout or []:
                    q.put(line)
            finally:
                q.put(f"[{service}] log stream ended.\n")

        t = threading.Thread(target=_reader, daemon=True)
        self.log_threads[service] = t
        t.start()

    def stop_log_tail(self, service: str) -> None:
        proc = self.log_procs.get(service)
        if not proc:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self.log_procs.pop(service, None)

    def _schedule_log_pump(self) -> None:
        for service, q in self.log_queues.items():
            while not q.empty():
                msg = q.get_nowait()
                self._append_log(service, msg)
        self.root.after(200, self._schedule_log_pump)


def main() -> None:
    config_path = Path(os.getenv("CONTROL_HUB_CONFIG", "config.json")).resolve()
    root = tk.Tk()
    ControlHubUI(root, config_path)
    root.mainloop()


if __name__ == "__main__":
    main()
