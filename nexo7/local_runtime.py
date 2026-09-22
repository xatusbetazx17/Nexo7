"""Managed local inference. Refuse unbounded or remotely hosted Docker engines."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import queue
import re
import threading
from .config import Config
from .hardware import ABSOLUTE_RAM_LIMIT, GB, detect_hardware, plan_local
from .net import TransportError, fetch_json

NAME = "nexo7-local-v2"
VOLUME = "nexo7-models-v2"
OWNER = "dev.nexo7.runtime"
OWNER_VALUE = "bounded-v2"
PORT = 11537
URL = f"http://127.0.0.1:{PORT}"


class SetupCancelled(ValueError):
    pass


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise SetupCancelled("Setup was cancelled")


def docker(args, timeout=15, live=False, emit=None, cancel=None):
    if not shutil.which("docker"):
        raise ValueError("Docker is missing. Install and start Docker with Linux containers to use bounded local inference.")
    environment = os.environ.copy()
    if "LD_LIBRARY_PATH_ORIG" in environment:
        environment["LD_LIBRARY_PATH"] = environment["LD_LIBRARY_PATH_ORIG"]
    elif getattr(__import__("sys"), "frozen", False):
        environment.pop("LD_LIBRARY_PATH", None)
    options = {"env": environment, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    try:
        _check_cancel(cancel)
        if live and emit is not None:
            lines = queue.Queue(maxsize=100)
            with subprocess.Popen(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", **options) as process:
                def read():
                    for line in process.stdout:
                        clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()[-500:]
                        try:
                            lines.put_nowait(clean)
                        except queue.Full:
                            pass
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                deadline = time.monotonic() + timeout
                try:
                    while process.poll() is None or not lines.empty():
                        _check_cancel(cancel)
                        if time.monotonic() > deadline:
                            raise subprocess.TimeoutExpired("docker", timeout)
                        try:
                            line = lines.get(timeout=0.2)
                            if line:
                                emit(line)
                        except queue.Empty:
                            pass
                except BaseException:
                    process.kill()
                    process.wait(timeout=5)
                    raise
                result = subprocess.CompletedProcess(args, process.wait(), "")
                reader.join(timeout=1)
        else:
            result = subprocess.run(["docker", *args], capture_output=not live, text=True,
                                    timeout=timeout, check=False, **options)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Docker timed out; the local runtime is unavailable") from exc
    if result.returncode:
        # Do not forward daemon text, environment variables or command output to a chat.
        raise ValueError("Docker could not complete the operation. Check that it is running, disk space and GPU drivers.")
    return result.stdout or ""


def docker_json(args):
    try:
        return json.loads(docker(args))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid Docker response") from exc


def local_daemon():
    # Context flags/DOCKER_HOST may otherwise silently direct writes to another PC.
    endpoint = os.environ.get("DOCKER_HOST", "")
    contexts = docker_json(["context", "inspect"])
    if os.environ.get("DOCKER_CONTEXT") or not endpoint:
        if not isinstance(contexts, list) or not contexts:
            raise ValueError("The local Docker context could not be verified")
        endpoint = contexts[0].get("Endpoints", {}).get("docker", {}).get("Host", "")
    if not endpoint.startswith(("unix://", "npipe://")):
        raise ValueError("A local Docker engine using a Unix socket or named pipe is required; remote TCP/SSH engines are refused")
    info = docker_json(["info", "--format", "{{json .}}"])
    if info.get("OSType") != "linux" or info.get("CgroupVersion") != "2":
        raise ValueError("Linux containers and cgroups v2 are required to verify the RAM limit")
    if info.get("MemoryLimit") is not True or info.get("SwapLimit") is not True:
        raise ValueError("Docker did not confirm RAM and swap limit support; the model will not start")
    if type(info.get("MemTotal")) is not int or info["MemTotal"] <= 0:
        raise ValueError("Docker did not report available memory")
    return info


def existing_container():
    identifiers = docker(["ps", "-a", "--filter", "name=^/" + NAME + "$", "--format", "{{.ID}}"])
    if not identifiers.strip():
        return None
    item = docker_json(["inspect", NAME])[0]
    if item.get("Config", {}).get("Labels", {}).get(OWNER) != OWNER_VALUE:
        raise ValueError("The reserved container name belongs to another application; it was left unchanged")
    return item


def runtime_command(plan, backend):
    limit = plan["ram_limit_bytes"]
    if type(limit) is not int or not 0 < limit <= ABSOLUTE_RAM_LIMIT:
        raise ValueError("RAM budget exceeds the 16 GB maximum")
    args = ["run", "-d", "--name", NAME, "--label", OWNER + "=" + OWNER_VALUE,
            "--memory", str(limit), "--memory-swap", str(limit), "--cpus", str(plan["threads"]),
            "--pids-limit", "256", "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--publish", f"127.0.0.1:{PORT}:11434", "--volume", VOLUME + ":/root/.ollama"]
    environment = {"OLLAMA_NO_CLOUD": "1", "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1",
                   "OLLAMA_MAX_QUEUE": "1", "OLLAMA_KEEP_ALIVE": "2m", "OLLAMA_CONTEXT_LENGTH": "8192"}
    image = "ollama/ollama:latest"
    if backend == "nvidia":
        args += ["--gpus", "device=" + str(plan.get("gpu_index", 0))]
    elif backend == "amd":
        args += ["--device", "/dev/kfd", "--device", "/dev/dri"]
        image = "ollama/ollama:rocm"
    else:
        environment.update(CUDA_VISIBLE_DEVICES="-1", HIP_VISIBLE_DEVICES="-1", OLLAMA_VULKAN="0")
    for key, value in environment.items():
        args += ["--env", key + "=" + value]
    return args + [image]


def verify_record(record, expected_limit, expected_id):
    host = record.get("HostConfig", {})
    cfg = record.get("Config", {})
    if not record.get("State", {}).get("Running") or record.get("Id") != expected_id:
        raise ValueError("The local runtime changed or stopped; start local mode again")
    if cfg.get("Labels", {}).get(OWNER) != OWNER_VALUE:
        raise ValueError("This runtime is not the bounded Nexo container")
    if not 0 < expected_limit <= ABSOLUTE_RAM_LIMIT:
        raise ValueError("Invalid limit")
    if host.get("Memory") != expected_limit or host.get("MemorySwap") != expected_limit:
        raise ValueError("The RAM/swap limit changed; the query was blocked")
    if host.get("Privileged") or host.get("OomKillDisable") or host.get("NetworkMode") == "host":
        raise ValueError("Runtime isolation settings changed")
    bindings = host.get("PortBindings", {}).get("11434/tcp", [])
    if bindings != [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}]:
        raise ValueError("The local runtime port changed")
    environment = dict(entry.split("=", 1) for entry in cfg.get("Env", []) if "=" in entry)
    for key in ("OLLAMA_NO_CLOUD", "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_QUEUE"):
        if environment.get(key) != "1":
            raise ValueError("Concurrency or local execution limits changed")


def verify_kernel_limits(output, expected_limit):
    values = output.strip().splitlines()
    if len(values) != 2 or values[0].strip() != str(expected_limit) or values[1].strip() != "0":
        raise ValueError("The kernel did not confirm the hard RAM limit and disabled swap; query blocked")


def verify_runtime(config):
    if not config.local_container_id or config.ollama_url.rstrip("/") != URL:
        raise ValueError("Use the Nexo local launcher: external Ollama servers cannot provide the required RAM guard")
    local_daemon()
    record = docker_json(["inspect", config.local_container_id])[0]
    verify_record(record, config.local_ram_limit_bytes, config.local_container_id)
    actual = docker(["exec", config.local_container_id, "cat", "/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.swap.max"])
    verify_kernel_limits(actual, config.local_ram_limit_bytes)
    hardware = detect_hardware(probe_gpu=False)
    if hardware.available_bytes < GB:
        raise ValueError("Less than 1 GB RAM is available or measurement failed; close applications and retry")
    return record


def inference_options(config):
    options = {"num_predict": config.max_output_tokens, "num_ctx": config.ollama_context_tokens,
               "num_batch": 64, "num_thread": config.local_threads}
    if config.local_backend == "cpu":
        options["num_gpu"] = 0
    return options


def runtime_metrics(config):
    values = docker(["exec", config.local_container_id, "cat", "/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.peak"]).splitlines()
    return {"ram_current_bytes": int(values[0]), "ram_peak_bytes": int(values[1]),
            "ram_limit_bytes": config.local_ram_limit_bytes}


def config_from_plan(plan, profile, identifier, database):
    return Config(provider="ollama", model=profile["model"], ollama_url=URL,
                  ollama_context_tokens=profile["context_tokens"], local_container_id=identifier,
                  local_ram_limit_bytes=plan["ram_limit_bytes"], local_threads=plan["threads"],
                  local_backend=plan["backend"], database=str(database), history_messages=4,
                  max_context_chars=6000,
                  max_output_tokens=256 if plan.get("performance") == "fast" else 512,
                  max_model_calls=2 if plan.get("performance") == "fast" else 3,
                  max_total_output_tokens=512 if plan.get("performance") == "fast" else 1536,
                  timeout_seconds=180)


def _wait_ready(cancel=None):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        _check_cancel(cancel)
        try:
            fetch_json(URL + "/api/tags", timeout=2)
            return
        except TransportError:
            time.sleep(0.3)
    raise ValueError("The local runtime could not start")


def _remove_owned():
    if existing_container():
        docker(["rm", "-f", NAME], timeout=30)


def start_local(database, *, cpu_only=False, emit=print, cancel=None, performance="balanced"):
    _check_cancel(cancel)
    info = local_daemon()
    hardware = detect_hardware()
    plan = plan_local(hardware, info["MemTotal"], cpu_only, performance)
    _remove_owned()  # Only this dedicated runtime; model volume and external Ollama are preserved.
    backends = [plan["backend"]] + (["cpu"] if plan["backend"] != "cpu" else [])
    last_error = ""
    for backend in backends:
        current_plan = plan_local(detect_hardware(), info["MemTotal"], backend == "cpu", performance)
        backend = current_plan["backend"]  # Respect a fresh low-VRAM CPU fallback.
        emit(f"Backend {backend}; RAM limit {current_plan['ram_limit_bytes'] / GB:.2f} GB. Initial downloads depend on the selected profile.")
        try:
            docker(runtime_command(current_plan, backend), timeout=900, live=True, emit=emit, cancel=cancel)
            identifier = docker_json(["inspect", NAME])[0]["Id"]
            _wait_ready(cancel)
            for profile in current_plan["profiles"]:
                _check_cancel(cancel)
                config = config_from_plan(current_plan, profile, identifier, database)
                verify_runtime(config)  # Before downloads and before the first model allocation.
                emit("Preparing " + profile["model"] + " (may download several GB).")
                # A download failure is not evidence of RAM pressure; don't download other models blindly.
                docker(["exec", identifier, "ollama", "pull", profile["model"]], timeout=1800, live=True, emit=emit, cancel=cancel)
                tags = fetch_json(URL + "/api/tags", timeout=10)
                match = next((m for m in tags.get("models", []) if m.get("name") == profile["model"]), None)
                if not match or type(match.get("size")) is not int or match["size"] > profile["max_download"]:
                    raise ValueError("The downloaded model does not match the expected profile size")
                try:
                    verify_runtime(config)
                    # Load then unload inside the already enforced RAM budget; no paid API.
                    loaded = fetch_json(URL + "/api/generate", payload={"model": profile["model"], "prompt": "",
                        "stream": False, "keep_alive": 0, "options": inference_options(config)}, timeout=180)
                    if loaded.get("error"):
                        raise TransportError("The model could not load")
                    verify_runtime(config)
                except (TransportError, ValueError):
                    emit("This profile could not load; trying a smaller model with the same RAM limit.")
                    # Unload any partially running model before a smaller candidate.
                    try:
                        fetch_json(URL + "/api/generate", payload={"model": profile["model"], "keep_alive": 0}, timeout=10)
                    except TransportError:
                        pass
                    continue
                _check_cancel(cancel)
                emit("Ready: " + profile["model"] + ". Performance and languages need evaluation on this computer.")
                return config, current_plan
            last_error = "No profile completed loading."
        except SetupCancelled:
            _remove_owned()
            raise
        except (ValueError, TransportError) as exc:
            last_error = str(exc)
        _remove_owned()
        if backend != "cpu":
            emit("GPU setup failed; trying CPU with the same RAM protection.")
    raise ValueError(last_error + " An unbounded runtime will not be started.")


def stop_local():
    local_daemon()
    if existing_container():
        docker(["stop", "--time", "5", NAME], timeout=20)


def write_local_config(path, config):
    # Dedicated generated file; don't overwrite the user's existing config.toml.
    from dataclasses import asdict
    lines = ["# Generated by Nexo local launcher. RAM limit is checked at every model call."]
    for key, value in asdict(config).items():
        if isinstance(value, bool):
            encoded = str(value).lower()
        elif isinstance(value, str):
            encoded = json.dumps(value, ensure_ascii=False)
        else:
            encoded = str(value)
        lines.append(key + " = " + encoded)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
