# Resource policy

All GB figures in this project are decimal bytes. Sixteen GB is 16,000,000,000 bytes, not 16 GiB.

The planner reserves the greater of 2 GB or 20% of host RAM. It selects a model-container budget no larger than 12 GB, 65% of host RAM, available RAM minus that reserve, and 65% of Docker VM memory when applicable. Unknown memory or inadequate free RAM blocks local setup. Config accepts no limit above 16 GB.

| Model profile | Minimum container budget | Model download admission cap |
| --- | ---: | ---: |
| qwen3.5:0.8b | 2.5 GB | 1.5 GB |
| qwen3.5:2b | 4.8 GB | 3.2 GB |
| qwen3.5:4b | 6.0 GB | 4.2 GB |
| qwen3.5:9b | 10.0 GB | 7.5 GB |

These are conservative policy thresholds, not measured performance guarantees. CPU/AMD planning stops at 4B. NVIDIA planning can consider 9B if measured free VRAM, less a reserve of max(512 MB, 20% of total VRAM), exceeds the profile download cap plus 256 MB. The GPU with most free VRAM is selected. This is an estimate, not a hard VRAM limit; driver/runtime overhead may still force CPU fallback. Unsupported acceleration falls back to CPU. An unsuccessful initial model load can fall back to a smaller profile without increasing the limit.

Docker receives identical `--memory` and `--memory-swap` values. Before allocating the model, and before subsequent inference, Nexo validates the container identity, configured limits, local binding, concurrency settings, and actual `memory.max` / `memory.swap.max` values. The latter must equal the configured byte count and zero. The kernel can terminate the model under pressure; Nexo reports failure instead of raising its budget.

The bound covers the model-server container's charged RAM. It excludes host OS memory, the Python application, browser, Docker VM overhead and dedicated GPU VRAM. Shared/unified GPU allocations and driver behavior need platform-specific validation; no whole-system RAM guarantee is made. Container images and accumulated model downloads are not part of the per-model size cap.

Fast chooses at most 0.8B on hosts up to 8.6 GB or 2B above that. Balanced CPU selection on hosts up to 8.6 GB stops at 2B. Context is capped at 6144 tokens below a 6 GB container budget, otherwise 8192. Fast generation is capped at 256 tokens/call and 512 total; normal local settings use 512/call and 1536 total. Hardware is measured during setup and each automatic launch; there is no live model resizing during a response.

Resource measurements and kernel enforcement must still be validated on actual target hardware. This development environment has no Docker daemon or GPU available. The unit suite checks policy and failure handling using fixtures; it is not an end-to-end inference test.
