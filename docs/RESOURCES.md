# Native resource policy — 0.5

All GB figures use decimal bytes. The planner reserves max(2 GB, 20% of host RAM), then budgets min(12 GB, 65% of host RAM, currently available RAM minus reserve). Free memory is checked again after downloads. Configuration rejects values above 16 GB. Insufficient or unknown free memory blocks setup.

Profiles keep minimum budgets of 2.5/4.8/6/10 GB for 0.8B/2B/4B/9B Qwen3.5. Pinned Q4_K_M downloads are approximately 0.58/1.40/3.01/6.17 GB. CPU selects at most 4B; Fast always chooses 0.8B. Context is capped at 6144. One model/request is active at a time. Initial load failure can try a smaller model without increasing the budget. Downloads may accumulate on disk; there is no 16 GB total-installation cap.

Linux: a separate supervisor sets and verifies hard/soft RLIMIT_AS before spawning the native model. The address-space ceiling is inherited; the runtime cannot increase it. Linux GPU drivers may reserve huge virtual address ranges, so this native edition uses CPU. The limit includes mapped addresses, not just resident RAM; allocation can fail with free physical RAM remaining. The Python supervisor has the same per-process bound, not a shared aggregate bound.

Windows: a separate supervisor creates a Job Object with JOB_OBJECT_LIMIT_JOB_MEMORY and JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, verifies it, joins it, then starts the model. Descendants inherit the job. The bound applies to aggregate committed memory, not every file-backed mapping. Model loading disables mmap to account for model buffers as allocations. Windows can attempt Vulkan on the first detected NVIDIA GPU when its free VRAM is measurable; setup falls back to CPU if loading fails. VRAM estimates are not kernel-enforced caps.

The parent owns a pipe to the supervisor. EOF triggers shutdown even after an app crash; Windows job close also kills descendants. Native requests require an in-process ownership record and a live supervisor. The model server is loopback-only with a random API key, no Web UI, no agent/shell/MCP tools, one inference slot and no prompt cache. An inherited llama/GGML configuration is stripped from its environment.

Native mode does not disable swapping and is not a security sandbox. Other processes, OS memory, browser, application, drivers and dedicated VRAM are outside the bound. Actual resource and GPU behavior still need validation on each target hardware class. Automated tests include a real rejected over-budget allocation on the OS, not only mocked decisions.

Legacy Docker/Ollama code remains for existing advanced configurations. Its old cgroup/swap policy is separate; the desktop and `local` command no longer require it.
