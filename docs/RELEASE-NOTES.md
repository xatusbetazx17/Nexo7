# Nexo 7 0.5.0 — native local assistant

- Runs directly on Windows/Linux; the desktop no longer requires Docker or WSL.
- Pinned SHA-256-verified native engine and GGUF downloads, reusable offline after initial setup.
- OS-specific memory guards, automatic CPU/model fallback and cleanup when Nexo closes.
- PDF/DOCX/text import with a limited extraction worker and review before saving.
- Local workspace read tools, CSV statistics, JSON validation, Python syntax inspection and calendar arithmetic.
- Native Windows/Linux executable builds and real-model desktop smoke tests gate publication.

Windows Vulkan/NVIDIA is experimental; native Linux uses CPU to retain the strict virtual-address-space limit. No universal compatibility, model superiority or autonomous learning claim. Output can be wrong. The memory budget excludes app/browser, OS, dedicated VRAM and disk storage; Windows committed memory and Linux address space are different measures. Binaries are unsigned previews. Download models once before offline use.
