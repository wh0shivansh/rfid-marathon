import json
import os
import subprocess
import sys
import threading
import queue
import time
import socket
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from enum import Enum

class ServiceType(str, Enum):
    """Enumeration of service types"""
    ACTIVE = "active"
    DISABLED = "disabled"
    HIDDEN = "hidden"
    OTHER = "other"

DEFAULT_CONFIG = {
    "services": [
        {"name": "database", "path": "", "type": ServiceType.ACTIVE},
        {"name": "rfid-backend", "path": "rfid-backend/rfid-backend.exe", "type": ServiceType.ACTIVE},
        {"name": "rfid-listener", "path": "rfid-listener/rfid-listener.exe", "type": ServiceType.ACTIVE},
        {"name": "marathon-ui", "path": "marathon-win32-x64/marathon.exe", "type": ServiceType.ACTIVE},
        {"name": "udp-listener", "path": "udp-listener/udp-listener.exe", "type": ServiceType.DISABLED},
        {"name": "udp-sender", "path": "udp-sender/udp-sender.exe", "type": ServiceType.DISABLED},
        {"name": "tag-web-server", "path": "tag_web_server/tag_server_20230711.exe", "type": ServiceType.OTHER},
    ]
}

DEFAULT_SERVICE_ORDER = [svc["name"] for svc in DEFAULT_CONFIG["services"]]


def resolve_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent

    if (base_dir / "rfid-backend").exists():
        return base_dir
    if (base_dir / "RFID-Marathon-Automation").exists():
        return (base_dir / "RFID-Marathon-Automation").resolve()
    if (base_dir.parent / "RFID-Marathon-Automation").exists():
        return (base_dir.parent / "RFID-Marathon-Automation").resolve()
    return base_dir


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return DEFAULT_CONFIG.copy()
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data or {})
    return merged


def normalize_services(services: list[dict]) -> list[dict]:
    def parse_service_type(raw_type: object) -> ServiceType:
        if isinstance(raw_type, ServiceType):
            return raw_type
        if isinstance(raw_type, str):
            try:
                return ServiceType(raw_type.strip().lower())
            except ValueError:
                return ServiceType.HIDDEN
        return ServiceType.HIDDEN

    normalized = []
    for svc in services:
        if isinstance(svc, str):
            normalized.append(
                {
                    "name": svc,
                    "path": svc,
                    "args": [],
                    "cwd": None,
                    "type": ServiceType.ACTIVE,
                }
            )
            continue
        name = svc.get("name") or svc.get("path") or "service"
        normalized.append(
            {
                "name": name,
                "path": svc.get("path", ""),
                "args": svc.get("args", []),
                "cwd": svc.get("cwd"),
                "type": parse_service_type(svc.get("type", ServiceType.ACTIVE)),
            }
        )
    return normalized


class ControlHubUI:
    def __init__(self, root: tk.Tk, config_path: Path, runtime_root: Path):
        self.root = root
        self.config_path = config_path
        self.runtime_root = runtime_root
        self.debug_enabled = os.getenv("CONTROL_HUB_DEBUG", "").strip() not in {"", "0"}
        self.config = load_config(config_path)
        self.services = normalize_services(
            self.config.get("services") or DEFAULT_CONFIG["services"]
        )
        # Ensure `database` appears as a managed service so it shows up in
        # service lists and Start/Stop All flows.
        if not any(svc.get("name") == "database" for svc in self.services):
            self.services.append(
                {
                    "name": "database",
                    "path": "",
                    "args": [],
                    "cwd": None,
                    "type": ServiceType.ACTIVE,
                }
            )
        self.service_map = {svc["name"]: svc for svc in self.services}
        self.display_services = self._build_display_services()

        self.log_queues: dict[str, queue.Queue[str]] = {}
        self.log_threads: dict[str, threading.Thread] = {}
        self.log_procs: dict[str, subprocess.Popen] = {}
        self.log_text_widgets: dict[str, tk.Text] = {}
        self.service_vars: dict[str, tk.BooleanVar] = {}
        self.exited_services: set[str] = set()
        self.group_vars: dict[str, tk.BooleanVar] = {}
        self.search_vars: dict[str, tk.StringVar] = {}
        self.search_after_ids: dict[str, str] = {}
        self.log_file_paths: dict[str, Path] = {}
        self.log_tab_index: dict[str, int] = {}
        self.setup_queue: queue.Queue[str] = queue.Queue()
        self.backend_start_lock = threading.Lock()
        self.backend_start_event = threading.Event()
        self.backend_start_failed = False
        self.database_start_lock = threading.Lock()
        self.database_start_event = threading.Event()
        self.database_start_failed = False
        self.db_setup_proc: subprocess.Popen | None = None
        self.db_stop_event = threading.Event()

        self._build_ui()
        self._schedule_log_pump()

    def _build_display_services(self) -> list[dict]:
        ordered = self._services_in_priority_order(include_hidden=False)
        return [svc for svc in ordered if svc.get("type") != ServiceType.HIDDEN]

    def _services_in_priority_order(self, include_hidden: bool) -> list[dict]:
        priority = {name: i for i, name in enumerate(DEFAULT_SERVICE_ORDER)}
        indexed = []
        for idx, svc in enumerate(self.services):
            if not include_hidden and svc.get("type") == ServiceType.HIDDEN:
                continue
            indexed.append((idx, svc))
        indexed.sort(
            key=lambda item: (
                priority.get(item[1]["name"], len(priority) + item[0]),
                item[0],
            )
        )
        return [svc for _, svc in indexed]

    def _is_active_service(self, svc: dict | None) -> bool:
        if not svc:
            return False
        return svc.get("type") == ServiceType.ACTIVE

    def _build_ui(self) -> None:
        self.root.title("RFID Marathon Control Hub")
        self.root.geometry("1100x800")
        self.root.minsize(900, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Control Hub", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        ttk.Button(top_frame, text="Clear All Logs", command=self.clear_all_logs).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(top_frame, text="Status", command=self.show_status).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Restart All", command=self.restart_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Stop All", command=self.stop_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="Start All", command=self.start_all).pack(side=tk.RIGHT, padx=4)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        services_frame = ttk.LabelFrame(main_frame, text="Services", padding=10)
        services_frame.pack(side=tk.LEFT, fill=tk.Y)

        self._build_service_controls(services_frame)

        logs_frame = ttk.LabelFrame(main_frame, text="Logs", padding=10)
        logs_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.logs_notebook = ttk.Notebook(logs_frame)
        self.logs_notebook.pack(fill=tk.BOTH, expand=True)

        tab_index = 0
        for svc in self.display_services:
            name = svc["name"]
            if name in {"marathon-ui", "database"}:
                continue
            tab = ttk.Frame(self.logs_notebook)
            self.logs_notebook.add(tab, text=name)
            self.log_tab_index[name] = tab_index
            tab_index += 1

            toolbar = ttk.Frame(tab)
            toolbar.pack(fill=tk.X, pady=(0, 6))

            ttk.Button(
                toolbar,
                text="Clear Log",
                command=lambda s=name: self.clear_log(s),
            ).pack(side=tk.LEFT)

            ttk.Label(toolbar, text="Find:").pack(side=tk.LEFT, padx=(10, 4))
            search_var = tk.StringVar()
            self.search_vars[name] = search_var
            entry = ttk.Entry(toolbar, textvariable=search_var)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entry.bind("<Return>", lambda event, s=name: self.search_log(s))
            search_var.trace_add("write", lambda *_args, s=name: self.schedule_search(s))

            ttk.Button(
                toolbar,
                text="Search",
                command=lambda s=name: self.search_log(s),
            ).pack(side=tk.LEFT, padx=4)
            ttk.Button(
                toolbar,
                text="Clear",
                command=lambda s=name: self.clear_search(s),
            ).pack(side=tk.LEFT)

            text = tk.Text(tab, wrap=tk.NONE, font=("Consolas", 10))
            text.pack(fill=tk.BOTH, expand=True)
            text.configure(state=tk.DISABLED)
            self.log_text_widgets[name] = text

        self.status_text = tk.Text(self.root, height=6, wrap=tk.NONE, font=("Consolas", 10))
        self.status_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._append_status("Control Hub ready.\n")

    def _append_status(self, message: str) -> None:
        self.status_text.configure(state=tk.NORMAL)
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED)

    def _debug(self, message: str) -> None:
        if self.debug_enabled:
            self._append_status(message)

    def _append_log(self, service: str, message: str) -> None:
        text = self.log_text_widgets.get(service)
        if not text:
            return
        text.configure(state=tk.NORMAL)
        text.insert(tk.END, message)
        text.see(tk.END)
        text.configure(state=tk.DISABLED)
        self._append_log_file(service, message)

    def _run_database_setup(self) -> int:
        bundle_dir = self.runtime_root / "database-setup"
        target_bin_dir = bundle_dir / "postgres" / "bin"

        if not bundle_dir.exists():
            self.setup_queue.put("[db-setup] Missing database-setup folder.\n")
            return 1
        if not (bundle_dir / "build_database.ps1").exists():
            self.setup_queue.put("[db-setup] Missing build_database.ps1 in database-setup.\n")
            return 1
        if not (bundle_dir / ".env").exists():
            self.setup_queue.put("[db-setup] Missing .env in database-setup.\n")
            return 1
        if not (bundle_dir / "init.sql").exists():
            self.setup_queue.put("[db-setup] Missing init.sql in database-setup.\n")
            return 1
        if not (target_bin_dir / "postgres.exe").exists():
            self.setup_queue.put("[db-setup] PostgreSQL binaries not found in database-setup/postgres/bin.\n")
            return 1

        self.setup_queue.put("[db-setup] Running local PostgreSQL setup...\n")
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Detach the DB setup process from the Control Hub process group so
            # the spawned PostgreSQL server isn't terminated when this app exits.
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

        self._append_status(f"[debug] Launching build_database.ps1: {bundle_dir / 'build_database.ps1'} cwd={bundle_dir}\n")
        # clear any previous stop request and track new process
        try:
            self.db_stop_event.clear()
        except Exception:
            pass

        proc = subprocess.Popen(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(bundle_dir / "build_database.ps1"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(bundle_dir),
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        # track the db setup process so we can terminate it if the user stops the DB
        try:
            self.db_setup_proc = proc
        except Exception:
            pass
        if proc.stdout:
            for line in proc.stdout:
                # preserve original line breaks
                self.setup_queue.put(f"[db-setup] {line}")
                # also write debug status for certain debug markers
                if line.strip().startswith("[debug]"):
                    self._append_status(f"{line}")
                # if a stop was requested, terminate the setup process
                try:
                    if self.db_stop_event.is_set():
                        try:
                            proc.terminate()
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        break
                except Exception:
                    pass
        proc.wait()
        try:
            # clear tracking on exit
            if self.db_setup_proc is proc:
                self.db_setup_proc = None
        except Exception:
            pass
        self.setup_queue.put(f"[db-setup] Setup finished with exit code {proc.returncode}.\n")
        self._append_status(f"[debug] build_database.ps1 exited with code {proc.returncode} at {time.asctime()}\n")
        # If a postgres.log exists in the bundle, append its tail for debugging
        try:
            pg_log = bundle_dir / "postgres.log"
            if pg_log.exists():
                text = pg_log.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail = "\n" + "\n".join(text[-100:]) + "\n"
                self._append_status("[debug] postgres.log tail:\n")
                self._append_status(tail)
        except Exception:
            pass
        return proc.returncode

    def _build_service_controls(self, services_frame: ttk.Frame | ttk.LabelFrame) -> None:
        frontend_var = tk.BooleanVar(value=False)
        endline_var = tk.BooleanVar(value=False)
        # Database is treated as a separate service controlled by its own checkbox.
        db_var = tk.BooleanVar(value=False)
        self.group_vars["frontend"] = frontend_var
        self.group_vars["endline"] = endline_var

        ttk.Checkbutton(
            services_frame,
            text="Frontend (depends on backend service)",
            variable=frontend_var,
            command=self.toggle_frontend_group,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Checkbutton(
            services_frame,
            text="End Line",
            variable=endline_var,
            command=self.toggle_endline_group,
        ).pack(anchor=tk.W)

        db_svc = self.service_map.get("database")
        if db_svc and db_svc.get("type") != ServiceType.HIDDEN:
            db_cb = ttk.Checkbutton(
                services_frame,
                text="Database (local)",
                variable=db_var,
                command=lambda: self.toggle_service("database"),
            )
            db_cb.pack(anchor=tk.W, pady=(6, 8), padx=(18, 0))
            if db_svc.get("type") == ServiceType.DISABLED:
                db_cb.state(["disabled"])
            # register as a service var so other code can read it
            self.service_vars["database"] = db_var

        self._add_service_checkbox(services_frame, "rfid-backend", "backend server", indent=True)
        self._add_service_checkbox(
            services_frame,
            "rfid-listener",
            "proxy server (rfid-listener)",
            indent=True,
        )
        self._add_service_checkbox(
            services_frame,
            "udp-listener",
            "udp-listener",
            indent=True,
        )

        ttk.Label(services_frame, text="Mid Line").pack(anchor=tk.W, pady=(8, 0))
        self._add_service_checkbox(
            services_frame,
            "udp-sender",
            "udp-sender",
            indent=True,
        )


        ttk.Separator(services_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        if "marathon-ui" in self.service_map and "marathon-ui" not in self.service_vars:
            self.service_vars["marathon-ui"] = tk.BooleanVar(value=False)

        extras = [
            svc
            for svc in self.display_services
            if svc["name"]
            not in {"marathon-ui", "rfid-backend", "rfid-listener", "udp-listener", "udp-sender", "database"}
        ]
        if extras:
            ttk.Label(services_frame, text="Other Services").pack(anchor=tk.W, pady=(4, 0))
            for svc in extras:
                self._add_service_checkbox(
                    services_frame,
                    svc["name"],
                    svc["name"],
                    indent=True,
                )

    def _add_service_checkbox(
        self,
        services_frame: tk.Misc,
        service_name: str,
        label: str,
        indent: bool = False,
    ) -> None:
        svc = self.service_map.get(service_name)
        if not svc:
            return
        var = tk.BooleanVar(value=False)
        self.service_vars[service_name] = var
        cb = ttk.Checkbutton(
            services_frame,
            text=label,
            variable=var,
            command=lambda s=service_name: self.toggle_service(s),
        )
        if svc.get("type") == ServiceType.DISABLED:
            cb.state(["disabled"])
        pad = (18, 0) if indent else (0, 0)
        cb.pack(anchor=tk.W, pady=2, padx=pad)

    def toggle_frontend_group(self) -> None:
        is_on = self.group_vars["frontend"].get()
        if is_on:
            backend_svc = self._find_service("rfid-backend")
            frontend_svc = self._find_service("marathon-ui")
            if self._is_active_service(backend_svc):
                self.service_vars.get("rfid-backend", tk.BooleanVar()).set(True)
                self.start_service("rfid-backend")
            if self._is_active_service(frontend_svc):
                self.service_vars.get("marathon-ui", tk.BooleanVar()).set(True)
                self.start_service("marathon-ui")
        else:
            self.service_vars.get("marathon-ui", tk.BooleanVar()).set(False)
            self.stop_service("marathon-ui")

    def toggle_endline_group(self) -> None:
        is_on = self.group_vars["endline"].get()
        # End Line should bring up local DB first, then backend, then listeners.
        targets = [
            name
            for name in ["database", "rfid-backend", "rfid-listener", "udp-listener"]
            if self._is_active_service(self._find_service(name))
        ]

        if is_on:
            for name in targets:
                self.service_vars.get(name, tk.BooleanVar()).set(True)
                self.start_service(name)
        else:
            for name in reversed(targets):
                self.service_vars.get(name, tk.BooleanVar()).set(False)
                self.stop_service(name)

    def _find_service(self, service: str) -> dict | None:
        for svc in self.services:
            if svc["name"] == service:
                return svc
        return None

    def _resolve_service_path(self, svc: dict) -> Path:
        raw_path = svc.get("path", "")
        if not raw_path:
            return Path("")
        path = Path(raw_path)
        if not path.is_absolute():
            path = (self.runtime_root / path).resolve()
        return path

    def _start_process(self, service: str, svc: dict) -> bool:
        if service in self.log_procs and self.log_procs[service].poll() is None:
            self._append_status(f"{service} is already running.\n")
            return False

        exe_path = self._resolve_service_path(svc)
        if not exe_path.exists():
            self._append_status(f"Executable not found for {service}: {exe_path}\n")
            return False

        args = svc.get("args") or []
        cwd = svc.get("cwd")
        if cwd:
            cwd_path = Path(cwd)
            if not cwd_path.is_absolute():
                cwd_path = (self.runtime_root / cwd_path).resolve()
        else:
            cwd_path = exe_path.parent

        # On Windows, start the process in a new process group so that
        # terminating this Control Hub process won't automatically terminate
        # other unrelated child processes (like a locally started PostgreSQL).
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            [str(exe_path), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(cwd_path),
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        self.log_procs[service] = proc
        self.exited_services.discard(service)

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
        return True

    def start_service(self, service: str) -> None:
        svc = self._find_service(service)
        if not svc:
            self._append_status(f"Unknown service: {service}\n")
            return
        svc_type = svc.get("type")
        if svc_type == ServiceType.HIDDEN:
            return
        if svc_type == ServiceType.DISABLED:
            self._append_status(f"{service} is disabled and cannot be started.\n")
            if service in self.service_vars:
                self.service_vars[service].set(False)
            self._sync_group_vars()
            return
        if service == "database":
            # Start the bundled DB setup asynchronously and reflect outcome
            def _worker_db() -> None:
                self._append_status("Starting local database setup...\n")
                code = self._run_database_setup()
                if code == 0:
                    self._append_status("Local database setup completed.\n")
                    try:
                        self.service_vars.get("database", tk.BooleanVar()).set(True)
                    except Exception:
                        pass
                else:
                    self._append_status("Local database setup failed.\n")
                    try:
                        self.service_vars.get("database", tk.BooleanVar()).set(False)
                    except Exception:
                        pass
                self._sync_group_vars()

            threading.Thread(target=_worker_db, daemon=True).start()
            return
        if service == "rfid-backend":
            # Respect the Database service checkbox. If enabled, run the bundled
            # DB setup + backend workflow; otherwise only start backend if an
            # external DB is already reachable.
            db_selected = self.service_vars.get("database", tk.BooleanVar(value=False)).get()
            if db_selected:
                self._ensure_backend_started_async(svc)
            else:
                # Check whether DB is reachable; if not, skip start.
                db_host = "localhost"
                db_port = 5432
                try:
                    env_path = (self.runtime_root / "database-setup" / ".env")
                    if env_path.exists():
                        for ln in env_path.read_text(encoding="utf-8").splitlines():
                            if not ln or ln.strip().startswith("#"):
                                continue
                            parts = ln.split("=", 2)
                            if len(parts) < 2:
                                continue
                            k = parts[0].strip()
                            v = parts[1].strip().strip('"')
                            if k == "DB_HOST":
                                db_host = v
                            elif k == "DB_PORT":
                                try:
                                    db_port = int(v)
                                except Exception:
                                    pass
                except Exception:
                    pass

                if not self._wait_for_db_ready(db_host, db_port, timeout_seconds=3.0):
                    self._append_status("Database not reachable; backend start skipped.\n")
                    self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                    self._sync_group_vars()
                else:
                    if self._start_process(service, svc):
                        self._append_status(f"Started {service}.\n")
                        self._sync_group_vars()
            return
        if service == "marathon-ui":
            self._start_frontend_with_backend(svc)
            return
        if self._start_process(service, svc):
            self._append_status(f"Started {service}.\n")
            self._sync_group_vars()

    def stop_service(self, service: str) -> None:
        proc = self.log_procs.get(service)
        if not proc:
            # handle database specially (may be a detached local server)
            if service == "database":
                def _stop_db_worker() -> None:
                    bundle_dir = self.runtime_root / "database-setup"
                    bin_dir = bundle_dir / "postgres" / "bin"
                    # Try pg_ctl if available and a data dir can be found
                    pg_ctl = bin_dir / "pg_ctl.exe"
                    possible_data_dirs = [
                        bundle_dir / "pgdata",
                        bundle_dir / "postgres" / "data",
                        bundle_dir / "postgres" / "pgdata",
                    ]
                    stopped = False
                    try:
                        # prepare flags to hide spawned consoles on Windows
                        startupinfo = None
                        creationflags = 0
                        if os.name == "nt":
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

                        if pg_ctl.exists():
                            for d in possible_data_dirs:
                                if d.exists():
                                    cmd = [str(pg_ctl), "stop", "-D", str(d), "-m", "fast"]
                                    self._append_status(f"Stopping local DB via pg_ctl: {d}\n")
                                    try:
                                        sub = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                        self._append_status(sub.stdout)
                                        if sub.returncode == 0:
                                            stopped = True
                                            break
                                    except Exception as e:
                                        self._append_status(f"pg_ctl stop failed: {e}\n")
                    except Exception:
                        pass

                    # Fallback: use PowerShell to stop postgres.exe processes whose
                    # ExecutablePath contains the bundle path.
                    if not stopped and os.name == "nt":
                        try:
                            # Also ensure any running build_database.ps1 is terminated
                            try:
                                db_proc = getattr(self, 'db_setup_proc', None)
                                if db_proc and db_proc.poll() is None:
                                    # signal the run loop to stop as well
                                    try:
                                        self.db_stop_event.set()
                                    except Exception:
                                        pass
                                    self._append_status('Terminating running build_database.ps1 process...\n')
                                    # Prefer taskkill to kill the process tree if available
                                    try:
                                        if os.name == 'nt' and getattr(db_proc, 'pid', None):
                                            subprocess.run(["taskkill", "/PID", str(db_proc.pid), "/T", "/F"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                    except Exception:
                                        pass
                                    try:
                                        db_proc.terminate()
                                    except Exception:
                                        try:
                                            db_proc.kill()
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                            exe_list = ['postgres.exe','pg_isready.exe','pg_ctl.exe','postmaster.exe']
                            # First, stop any process whose command line mentions build_database.ps1
                            try:
                                ps_cmd_cmdline = (
                                    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*build_database.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
                                )
                                self._append_status("Attempting to stop any processes running build_database.ps1 via PowerShell.\n")
                                proc_ps = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_cmdline], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                self._append_status(proc_ps.stdout)
                            except Exception:
                                pass

                            # Also stop known postgres bundle executables regardless of path
                            try:
                                name_filter = " -or ".join([f"$_.Name -eq '{n}'" for n in exe_list])
                                ps_cmd_names = (
                                    "Get-CimInstance Win32_Process | Where-Object { (" + name_filter + ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
                                )
                                self._append_status("Attempting to stop postgres-related executables via PowerShell.\n")
                                proc_ps2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_names], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                self._append_status(proc_ps2.stdout)
                            except Exception:
                                pass

                            # As a last resort, use taskkill to forcefully kill common executables
                            try:
                                if os.name == 'nt':
                                    for exe in exe_list:
                                        try:
                                            subprocess.run(["taskkill", "/F", "/IM", exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                            # Aggressive cleanup: repeat a few times to ensure any
                            # respawned or lingering pg_isready/pg_ctl/postgres
                            # processes are terminated.
                            try:
                                cleanup_deadline = time.time() + 5.0
                                while time.time() < cleanup_deadline:
                                    # kill by commandline mentioning build_database.ps1
                                    try:
                                        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_cmdline], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                    except Exception:
                                        pass
                                    # kill by executable name
                                    try:
                                        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_names], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                    except Exception:
                                        pass
                                    if os.name == 'nt':
                                        for exe in exe_list:
                                            try:
                                                subprocess.run(["taskkill", "/F", "/IM", exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, creationflags=creationflags)
                                            except Exception:
                                                pass
                                    # small delay between attempts
                                    time.sleep(0.4)
                            except Exception:
                                pass
                            stopped = True
                        except Exception as e:
                            self._append_status(f"PowerShell stop attempt failed: {e}\n")

                    if stopped:
                        try:
                            self.service_vars.get("database", tk.BooleanVar()).set(False)
                        except Exception:
                            pass
                        self._append_status("Local database stop attempted.\n")
                    else:
                        self._append_status("Could not deterministically stop local database; please stop it manually.\n")
                    self._sync_group_vars()

                threading.Thread(target=_stop_db_worker, daemon=True).start()
                return
            self._append_status(f"{service} is not running.\n")
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self.log_procs.pop(service, None)
        self._append_status(f"Stopped {service}.\n")
        if service == "rfid-backend":
            frontend_var = self.group_vars.get("frontend")
            if frontend_var and frontend_var.get():
                frontend_var.set(False)
                self.service_vars.get("marathon-ui", tk.BooleanVar()).set(False)
                self.stop_service("marathon-ui")
        self._sync_group_vars()

    def restart_service(self, service: str) -> None:
        self.stop_service(service)
        self.start_service(service)
        self._append_status(f"Restarted {service}.\n")

    def toggle_service(self, service: str) -> None:
        svc = self._find_service(service)
        if not svc:
            self._append_status(f"Unknown service: {service}\n")
            return
        svc_type = svc.get("type")
        if svc_type == ServiceType.HIDDEN:
            return
        if svc_type == ServiceType.DISABLED:
            self.service_vars.get(service, tk.BooleanVar()).set(False)
            self._append_status(f"{service} is disabled and cannot be started.\n")
            self._sync_group_vars()
            return
        if self.service_vars[service].get():
            self.start_service(service)
            if service in self.log_tab_index:
                self.logs_notebook.select(self.log_tab_index[service])
        else:
            self.stop_service(service)
        self._sync_group_vars()

    def start_all(self) -> None:
        for svc in self._services_in_priority_order(include_hidden=False):
            name = svc["name"]
            if svc.get("type") != ServiceType.ACTIVE:
                continue
            if name in self.service_vars:
                self.service_vars[name].set(True)
            self.start_service(name)
        self._sync_group_vars()

    def stop_all(self) -> None:
        for svc in self._services_in_priority_order(include_hidden=False):
            name = svc["name"]
            if svc.get("type") != ServiceType.ACTIVE:
                continue
            if name in self.service_vars:
                self.service_vars[name].set(False)
            self.stop_service(name)
        self._sync_group_vars()

    def _stop_all_services(self, include_hidden: bool) -> None:
        for svc in self._services_in_priority_order(include_hidden=include_hidden):
            name = svc["name"]
            if name in self.service_vars:
                self.service_vars[name].set(False)
            self.stop_service(name)
        self._sync_group_vars()

    def on_close(self) -> None:
        self._append_status("Shutting down services...\n")
        self._stop_all_services(include_hidden=True)
        self.root.destroy()

    def restart_all(self) -> None:
        for svc in self.services:
            self.restart_service(svc["name"])
        self._sync_group_vars()

    def show_status(self) -> None:
        for svc in self.services:
            name = svc["name"]
            proc = self.log_procs.get(name)
            if proc and proc.poll() is None:
                self._append_status(f"{name}: running\n")
            else:
                self._append_status(f"{name}: stopped\n")

    def _schedule_log_pump(self) -> None:
        for service, q in self.log_queues.items():
            while not q.empty():
                msg = q.get_nowait()
                self._append_log(service, msg)
        while not self.setup_queue.empty():
            msg = self.setup_queue.get_nowait()
            self._append_status(msg)
        for service, proc in list(self.log_procs.items()):
            if proc.poll() is not None and service not in self.exited_services:
                self.exited_services.add(service)
                self.service_vars[service].set(False)
                self._append_status(f"{service} exited with code {proc.returncode}.\n")
                self._sync_group_vars()
        self.root.after(200, self._schedule_log_pump)

    def _ensure_backend_started_async(self, svc: dict) -> None:
        if self.log_procs.get("rfid-backend") and self.log_procs["rfid-backend"].poll() is None:
            return
        if self.backend_start_event.is_set() and not self.backend_start_failed:
            return

        with self.backend_start_lock:
            if self.backend_start_event.is_set() and not self.backend_start_failed:
                return
            self.backend_start_event.clear()
            self.backend_start_failed = False

            def _worker() -> None:
                # First detect DB host/port settings for the bundled DB and
                # for the backend API. If a DB is already reachable, skip
                # running the bundled DB setup.
                db_host = "localhost"
                db_port = 5432
                try:
                    env_path = (self.runtime_root / "database-setup" / ".env")
                    if env_path.exists():
                        for ln in env_path.read_text(encoding="utf-8").splitlines():
                            if not ln or ln.strip().startswith("#"):
                                continue
                            parts = ln.split("=", 2)
                            if len(parts) < 2:
                                continue
                            k = parts[0].strip()
                            v = parts[1].strip().strip('"')
                            if k == "DB_HOST":
                                db_host = v
                            elif k == "DB_PORT":
                                try:
                                    db_port = int(v)
                                except Exception:
                                    pass
                except Exception:
                    pass

                # If a DB setup process is already running (for example from the
                # dedicated Database service), wait for readiness instead of
                # launching a second setup process.
                active_db_setup = self.db_setup_proc is not None and self.db_setup_proc.poll() is None
                if active_db_setup:
                    self._append_status("[debug] Database setup already running; waiting for DB readiness.\n")
                    if not self._wait_for_db_ready(db_host, db_port, timeout_seconds=60.0):
                        self.backend_start_failed = True
                        self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                        self._append_status("Database setup did not become ready in time.\n")
                        self._sync_group_vars()
                        self.backend_start_event.set()
                        return
                # If a DB is not accepting connections and no setup is active,
                # run the bundled setup now.
                elif not self._wait_for_db_ready(db_host, db_port, timeout_seconds=1.0):
                    exit_code = self._run_database_setup()
                    self._append_status(f"[debug] build_database.ps1 returned exit_code={exit_code}\n")
                    if exit_code != 0:
                        self.backend_start_failed = True
                        self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                        self._sync_group_vars()
                        self.backend_start_event.set()
                        return
                else:
                    self._append_status("[debug] Database already reachable; skipping bundled DB setup.\n")
                # Ensure the database is actually accepting connections before starting backend
                db_host = "localhost"
                db_port = 5432
                try:
                    env_path = (self.runtime_root / "database-setup" / ".env")
                    if env_path.exists():
                        for ln in env_path.read_text(encoding="utf-8").splitlines():
                            if not ln or ln.strip().startswith("#"):
                                continue
                            parts = ln.split("=", 2)
                            if len(parts) < 2:
                                continue
                            k = parts[0].strip()
                            v = parts[1].strip().strip('"')
                            if k == "DB_HOST":
                                db_host = v
                            elif k == "DB_PORT":
                                try:
                                    db_port = int(v)
                                except Exception:
                                    pass
                except Exception:
                    pass

                if not self._wait_for_db_ready(db_host, db_port, timeout_seconds=30.0):
                    self.backend_start_failed = True
                    self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                    self._sync_group_vars()
                    self.backend_start_event.set()
                    return

                self._append_status(f"[debug] backend env detection start\n")
                # Read backend API host/port to verify successful start
                app_host = "localhost"
                app_port = 8000
                try:
                    b_env = self.runtime_root / "rfid-backend" / ".env"
                    if b_env.exists():
                        for ln in b_env.read_text(encoding="utf-8").splitlines():
                            if not ln or ln.strip().startswith("#"):
                                continue
                            parts = ln.split("=", 2)
                            if len(parts) < 2:
                                continue
                            k = parts[0].strip()
                            v = parts[1].strip().strip('"')
                            if k == "APP_HOST":
                                app_host = v
                            elif k == "APP_PORT":
                                try:
                                    app_port = int(v)
                                except Exception:
                                    pass
                except Exception:
                    pass
                self._append_status(f"[debug] backend target host={app_host} port={app_port}\n")

                if self._start_process("rfid-backend", svc):
                    # give the process a short stable period and ensure API port is reachable
                    if not self._wait_for_service_running("rfid-backend", timeout_seconds=3.0):
                        # process exited quickly
                        self.backend_start_failed = True
                        self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                        self._append_status("rfid-backend exited immediately after start.\n")
                        self._sync_group_vars()
                        self.backend_start_event.set()
                        return

                    if not self._wait_for_db_ready(app_host, app_port, timeout_seconds=10.0):
                        # API not reachable; treat as failed
                        self.backend_start_failed = True
                        self.service_vars.get("rfid-backend", tk.BooleanVar()).set(False)
                        self._append_status("rfid-backend API not reachable after start.\n")
                        # Tail backend log for debugging
                        try:
                            log_path = self._get_log_file_path("rfid-backend")
                            if log_path.exists():
                                lines = log_path.read_text(encoding="utf-8").splitlines()
                                tail = "\n" + "\n".join(lines[-30:]) + "\n"
                                self._append_status("[debug] backend log tail:\n")
                                self._append_status(tail)
                        except Exception:
                            pass
                        self._sync_group_vars()
                        self.backend_start_event.set()
                        return

                    self._append_status("Started rfid-backend.\n")
                    self._sync_group_vars()
                    self.backend_start_event.set()
                else:
                    self.backend_start_failed = True
                    self.backend_start_event.set()

            threading.Thread(target=_worker, daemon=True).start()

    def _start_frontend_with_backend(self, svc: dict) -> None:
        def _worker() -> None:
            backend_var = self.service_vars.get("rfid-backend")
            if backend_var and not backend_var.get():
                backend_var.set(True)
                # If the user enabled the local Database service, run bundled
                # DB setup + backend workflow; otherwise attempt to start backend
                # only if an external DB is reachable.
                db_selected = self.service_vars.get("database", tk.BooleanVar(value=False)).get()
                if db_selected:
                    self._ensure_backend_started_async(self.service_map.get("rfid-backend", {}))
                else:
                    self.start_service("rfid-backend")
            if not self._wait_for_backend_ready(timeout_seconds=30.0):
                self._append_status("Backend did not start in time; frontend start skipped.\n")
                self.service_vars.get("marathon-ui", tk.BooleanVar()).set(False)
                self._sync_group_vars()
                return
            # Additionally wait until backend is accepting TCP connections (HTTP API)
            app_host = "localhost"
            app_port = 8000
            try:
                # check a few common locations for env files
                candidates = [
                    self.runtime_root / ".env",
                    self.runtime_root / "rfid-backend" / ".env",
                    self.runtime_root / "backend" / ".env",
                ]
                for p in candidates:
                    if p.exists():
                        for ln in p.read_text(encoding="utf-8").splitlines():
                            if not ln or ln.strip().startswith("#"):
                                continue
                            parts = ln.split("=", 2)
                            if len(parts) < 2:
                                continue
                            k = parts[0].strip()
                            v = parts[1].strip().strip('"')
                            if k == "APP_HOST":
                                app_host = v
                            elif k == "APP_PORT":
                                try:
                                    app_port = int(v)
                                except Exception:
                                    pass
                        break
            except Exception:
                pass

            if not self._wait_for_db_ready(app_host, app_port, timeout_seconds=30.0):
                self._append_status("Backend API did not become reachable; frontend start skipped.\n")
                self.service_vars.get("marathon-ui", tk.BooleanVar()).set(False)
                self._sync_group_vars()
                return

            if self._start_process("marathon-ui", svc):
                self._append_status("Started marathon-ui.\n")
                self._sync_group_vars()

        threading.Thread(target=_worker, daemon=True).start()

    def _wait_for_backend_ready(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.log_procs.get("rfid-backend") and self.log_procs["rfid-backend"].poll() is None:
                return True
            if self.backend_start_event.is_set() and self.backend_start_failed:
                return False
            time.sleep(0.2)
        return False

    def _wait_for_db_ready(self, host: str, port: int, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except Exception:
                time.sleep(0.5)
        return False

    def _wait_for_service_running(self, service: str, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            proc = self.log_procs.get(service)
            if proc and proc.poll() is None:
                return True
            time.sleep(0.2)
        return False

    def _sync_group_vars(self) -> None:
        endline_targets = [
            name
            for name in ["database", "rfid-backend", "rfid-listener", "udp-listener"]
            if self._is_active_service(self._find_service(name))
        ]
        endline_on = all(self.service_vars.get(name, tk.BooleanVar()).get() for name in endline_targets)
        frontend_on = self.service_vars.get("marathon-ui", tk.BooleanVar()).get()

        if "endline" in self.group_vars:
            self.group_vars["endline"].set(endline_on)
        if "frontend" in self.group_vars:
            self.group_vars["frontend"].set(frontend_on)

    def _get_log_file_path(self, service: str) -> Path:
        if service in self.log_file_paths:
            return self.log_file_paths[service]
        svc = self._find_service(service) or {"path": ""}
        exe_path = self._resolve_service_path(svc)
        if exe_path.exists():
            base_dir = exe_path.parent
        else:
            base_dir = self.runtime_root
        log_path = base_dir / f"{service}.log.txt"
        self.log_file_paths[service] = log_path
        return log_path

    def _append_log_file(self, service: str, message: str) -> None:
        log_path = self._get_log_file_path(service)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def clear_log(self, service: str) -> None:
        after_id = self.search_after_ids.pop(service, None)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        q = self.log_queues.get(service)
        flushed = 0
        if q:
            while not q.empty():
                try:
                    q.get_nowait()
                    flushed += 1
                except Exception:
                    break
        text = self.log_text_widgets.get(service)
        if text:
            text.configure(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            text.configure(state=tk.DISABLED)
        self.clear_search(service)
        self._debug(f"[debug] Cleared {service} log UI, flushed {flushed} queued lines.\n")
        log_path = self._get_log_file_path(service)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8"):
                pass
        except Exception:
            pass

    def clear_all_logs(self) -> None:
        for svc in self.display_services:
            self.clear_log(svc["name"])

    def search_log(self, service: str) -> None:
        text = self.log_text_widgets.get(service)
        if not text:
            return
        pattern = self.search_vars.get(service, tk.StringVar()).get()
        self.clear_search(service)
        if not pattern:
            return

        start = "1.0"
        first_match = None
        while True:
            idx = text.search(pattern, start, stopindex=tk.END, nocase=True)
            if not idx:
                break
            end = f"{idx}+{len(pattern)}c"
            text.tag_add("search_match", idx, end)
            if not first_match:
                first_match = idx
            start = end

        if first_match:
            text.tag_config("search_match", background="#ffd56a", foreground="#000000")
            text.see(first_match)

    def schedule_search(self, service: str) -> None:
        after_id = self.search_after_ids.get(service)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self.search_after_ids[service] = self.root.after(1500, lambda: self.search_log(service))

    def clear_search(self, service: str) -> None:
        text = self.log_text_widgets.get(service)
        if not text:
            return
        text.tag_remove("search_match", "1.0", tk.END)


def main() -> None:
    runtime_root = resolve_runtime_root()
    config_path = Path(os.getenv("CONTROL_HUB_CONFIG", runtime_root / "config.json")).resolve()
    root = tk.Tk()
    ControlHubUI(root, config_path, runtime_root)
    root.mainloop()


if __name__ == "__main__":
    main()
