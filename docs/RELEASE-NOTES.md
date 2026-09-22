# Nexo 7 0.4.0 — adaptive assistant preview

- Measured free NVIDIA VRAM guides profile selection and GPU choice; low VRAM falls back to CPU.
- Fast, Balanced and Larger-model preferences; language, reply style and optional automatic startup persist locally.
- User-approved examples become searchable documents. Incorrect feedback clears cached answers. Neither feature retrains model weights.
- My workspace saves, downloads and deletes reviewed documents and code without executing them.
- 70 core tests completed (69 passed, one optional PyTorch skip), expanded UI integration and Linux packaged smoke test.
- Four standalone real-model CPU cases, including an arithmetic failure, are documented in VALIDATION.md.

Extract the native release archive and run Nexo7 on Linux or Nexo7.exe on Windows. Python is bundled; Docker and model downloads are separate prerequisites. GitHub Actions builds and smoke-tests each native executable on its target OS. The separately distributed cross-compiled Windows preview remains an untested alternative. Binaries are unsigned. Native release packages are published only after both GitHub Actions build jobs pass. No universal model superiority or clinical capability is claimed.
