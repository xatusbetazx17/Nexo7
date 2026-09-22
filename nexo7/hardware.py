"""Read-only hardware discovery and conservative planning; sizes are decimal bytes."""
from dataclasses import asdict, dataclass
import ctypes
import os
from pathlib import Path
import platform
import re
import subprocess

GB = 1_000_000_000
ABSOLUTE_RAM_LIMIT = 16 * GB
OPERATING_RAM_LIMIT = 12 * GB


@dataclass(frozen=True)
class Hardware:
    system: str
    machine: str
    total_bytes: int
    available_bytes: int
    cpu_threads: int
    gpu_hint: str = "cpu"
    memory_source: str = "unknown"
    gpu_free_bytes: int = 0
    gpu_total_bytes: int = 0
    gpu_index: int = 0


@dataclass(frozen=True)
class Profile:
    model: str
    minimum_budget: int
    max_download: int
    context_tokens: int = 8192


# Download size is only an admission check, not an estimate of peak RAM.
PROFILES = (
    Profile("qwen3.5:0.8b", 2_500_000_000, 1_500_000_000, 6144),
    Profile("qwen3.5:2b", 4_800_000_000, 3_200_000_000),
    Profile("qwen3.5:4b", 6_000_000_000, 4_200_000_000),
    Profile("qwen3.5:9b", 10_000_000_000, 7_500_000_000),
)


def _output(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=4,
                              check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def linux_memory(proc=Path("/proc"), cgroup=Path("/sys/fs/cgroup")):
    entries = dict(re.findall(r"^(\w+):\s+(\d+)\s+kB", (proc / "meminfo").read_text(), re.M))
    total = int(entries.get("MemTotal", 0)) * 1024
    available = int(entries.get("MemAvailable", 0)) * 1024
    # Account for visible cgroup-v2 ancestors, including a container's namespace root.
    paths = [cgroup]
    try:
        relative = (proc / "self/cgroup").read_text().split("0::", 1)[1].splitlines()[0].lstrip("/")
        current = (cgroup / relative).resolve()
        if current.is_relative_to(cgroup.resolve()):
            paths.extend([current, *current.parents])
    except (OSError, IndexError):
        pass
    for directory in dict.fromkeys(paths):
        if not directory.resolve().is_relative_to(cgroup.resolve()):
            continue
        try:
            limit = (directory / "memory.max").read_text().strip()
            used = int((directory / "memory.current").read_text())
            if limit != "max":
                total = min(total, int(limit))
                available = min(available, max(0, int(limit) - used))
        except (OSError, ValueError):
            pass
    return total, min(total, available)


def detect_hardware(probe_gpu=True):
    system = platform.system()
    total = available = 0
    source = "unknown"
    try:
        if system == "Linux":
            total, available = linux_memory()
            source = "procfs + visible cgroup v2 limits"
        elif system == "Windows":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise OSError("GlobalMemoryStatusEx")
            total, available = int(status.total), int(status.available)
            source = "GlobalMemoryStatusEx"
        elif system == "Darwin":
            total = int(_output(["sysctl", "-n", "hw.memsize"]).strip())
            vm = _output(["vm_stat"])
            page = int(re.search(r"page size of (\d+) bytes", vm).group(1))
            # Exclude speculative/reclaimable estimates: conservative free + inactive.
            available = sum(int(re.search(label + r":\s+(\d+)", vm).group(1))
                            for label in ("Pages free", "Pages inactive")) * page
            source = "sysctl + vm_stat"
    except (OSError, ValueError, AttributeError):
        total = available = 0
        source = "unknown"
    try:
        threads = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        threads = os.cpu_count() or 1
    gpu = "cpu"
    gpu_free = gpu_total = gpu_index = 0
    if probe_gpu and _output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]).strip():
        readings = _output(["nvidia-smi", "--query-gpu=index,memory.free,memory.total", "--format=csv,noheader,nounits"])
        candidates = []
        for line in readings.splitlines():
            try:
                index, free, size = [int(value.strip()) for value in line.split(",")]
                if 0 <= free <= size and size > 0:
                    candidates.append((free * 1024**2, size * 1024**2, index))
            except ValueError:
                continue
        if candidates:
            gpu_free, gpu_total, gpu_index = max(candidates)
            gpu = "nvidia"
    elif probe_gpu and system == "Linux" and Path("/dev/kfd").exists() and Path("/dev/dri").exists():
        gpu = "amd"
    return Hardware(system, platform.machine(), total, min(total, available), threads, gpu, source, gpu_free, gpu_total, gpu_index)


def plan_local(hardware, daemon_memory=None, cpu_only=False, performance="balanced", *, native=False):
    if performance not in {"fast", "balanced", "quality"}:
        raise ValueError("Unknown performance preference")
    if hardware.total_bytes <= 0 or hardware.available_bytes <= 0:
        raise ValueError("Available RAM could not be measured; a model will not start without a verifiable budget.")
    # Available RAM already excludes memory occupied by the OS and other apps.
    # Native Windows needs extra headroom, not a second allowance for the whole OS.
    # Keep the larger legacy allowance for Docker VM overhead and Linux VA budgets.
    reserve = (max(GB, min(2 * GB, hardware.available_bytes // 4))
               if native and hardware.system == "Windows" and daemon_memory is None
               else max(2 * GB, hardware.total_bytes // 5))
    budget = min(OPERATING_RAM_LIMIT, hardware.total_bytes * 65 // 100,
                 max(0, hardware.available_bytes - reserve))
    if daemon_memory is not None:
        if type(daemon_memory) is not int or daemon_memory <= 0:
            raise ValueError("Available Docker memory is unknown")
        budget = min(budget, daemon_memory * 65 // 100)
    budget = budget // 1_000_000 * 1_000_000
    gpu = "cpu" if cpu_only else hardware.gpu_hint
    # Unknown VRAM never justifies a large GPU profile. AMD stays conservative.
    video_budget = max(0, hardware.gpu_free_bytes - max(512_000_000, hardware.gpu_total_bytes // 5))
    if gpu == "nvidia" and video_budget < PROFILES[0].max_download + 256_000_000:
        gpu = "cpu"
    candidates = [p for p in PROFILES if p.minimum_budget <= budget
                  and not (gpu in {"cpu", "amd"} and p.model.endswith(":9b"))
                  and (gpu != "nvidia" or p.max_download + 256_000_000 <= video_budget)]
    if performance == "fast":
        ceiling = 0 if hardware.total_bytes <= 8_600_000_000 else 1
        candidates = [p for p in candidates if p in PROFILES[:ceiling+1]]
    elif performance == "balanced" and gpu == "cpu" and hardware.total_bytes <= 8_600_000_000:
        candidates = [p for p in candidates if p in PROFILES[:2]]
    if not candidates:
        raise ValueError(f"Not enough available RAM: {hardware.available_bytes/GB:.2f} GB available, "
                         f"{reserve/GB:.2f} GB additional headroom, {budget/GB:.2f} GB model budget. "
                         f"The smallest profile needs {PROFILES[0].minimum_budget/GB:.2f} GB. "
                         "Close applications and check again, or use demo mode.")
    return {"hardware": asdict(hardware), "ram_limit_bytes": budget,
            "absolute_ram_ceiling_bytes": ABSOLUTE_RAM_LIMIT,
            "reserved_host_bytes": reserve, "backend": gpu,
            "threads": min(8, max(1, hardware.cpu_threads // 2)),
            "profiles": [{**asdict(p), "context_tokens": min(p.context_tokens, 6144 if budget < 6*GB else 8192)} for p in reversed(candidates)],
            "performance": performance, "gpu_index": hardware.gpu_index,
            "video_budget_bytes": video_budget if gpu == "nvidia" else None,
            "video_budget_enforced": False,
            "guard_scope": "Model server container RAM; excludes host OS, app/browser, Docker VM overhead and dedicated VRAM"}
