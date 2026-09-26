"""First-run setup state; every model launch retains the existing RAM guard."""
from dataclasses import asdict, replace
from pathlib import Path
import threading
from .config import Config
from .hardware import detect_hardware, plan_local
from .native_runtime import native_plan, start_native, stop_native


class SetupController:
    def __init__(self, database, preferences=None, save_preferences=None):
        self.config = Config(database=str(database))
        self.preferences = preferences or {"performance": "balanced", "cpu_only": False, "response_language": "auto", "auto_start": False}
        self.save_preferences = save_preferences
        self.operation = threading.Lock()
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.owns_runtime = False
        self.state = {"phase": "idle", "logs": [], "error": None, "report": None}

    def snapshot(self):
        with self.lock:
            return {**self.state, "logs": list(self.state["logs"]),
                    "ready": self.state["phase"] == "ready" and self.config.provider in {"native", "ollama"}}

    def emit(self, text):
        with self.lock:
            self.state["logs"].append(str(text)[-500:])
            self.state["logs"] = self.state["logs"][-80:]

    def check(self, cpu_only=False):
        hardware = detect_hardware()
        report = {"hardware": asdict(hardware), "requirements_ok":False, "plan":None, "error":None}
        try:
            report["plan"] = native_plan(cpu_only, self.preferences["performance"], model_choice=self.preferences.get("model_choice","automatic"))
            report["requirements_ok"] = True
        except (ValueError, OSError) as exc:
            report["error"] = str(exc)
        with self.lock:
            self.state["report"] = report
        return report

    def start(self, *, cpu_only=False, language="auto", switch=False):
        if type(cpu_only) is not bool:
            raise ValueError("cpu_only must be a boolean")
        language = Config(response_language=language).response_language
        if not self.operation.acquire(blocking=False):
            raise ValueError("A setup or chat operation is already running")
        with self.lock:
            if self.config.provider in {"native", "ollama"} and not (switch and self.owns_runtime and self.config.provider == "native"):
                self.operation.release()
                raise ValueError("The local model is already ready. Restart Nexo to change hardware settings.")
            self.cancel.clear()
            self.state.update(phase="preparing", logs=[], error=None)
        preferences = dict(self.preferences)
        def work():
            try:
                if self.owns_runtime:
                    self.emit("Unloading current model before switching…")
                    stop_native(self.config)
                    with self.lock:
                        self.config = Config(database=self.config.database)
                        self.owns_runtime = False
                self.emit("Checking native runtime and available memory…")
                config, plan = start_native(self.config.database, cpu_only=cpu_only,
                                          emit=self.emit, cancel=self.cancel, performance=preferences["performance"], model_choice=preferences.get("model_choice","automatic"))
                with self.lock:
                    self.config = replace(config, response_language=language)
                    self.owns_runtime = True
                    self.state.update(report={"requirements_ok": True, "plan": plan,
                                                             "hardware": plan["hardware"], "error": None})
                if self.save_preferences:
                    self.preferences = self.save_preferences({"cpu_only": cpu_only, "response_language": language})
                self.emit("Local model ready. You can start a conversation.")
            except Exception as exc:
                with self.lock:
                    self.state.update(phase="error", error=str(exc)[:500])
                self.emit("Setup stopped. Demo mode remains available.")
            finally:
                with self.lock:
                    self.operation.release()
                    if self.state["phase"] == "preparing" and self.owns_runtime:
                        self.state["phase"] = "ready"
        self.thread = threading.Thread(target=work, name="nexo-setup", daemon=True)
        self.thread.start()
        return self.snapshot()

    def close(self):
        self.cancel.set()
        if getattr(self,'image_generator',None):
            self.image_generator.close()
        if self.thread:
            self.thread.join()
        if self.owns_runtime:
            stop_native(self.config)
            self.owns_runtime = False
