# Nexo 7 0.6.2 — 4 GB available-memory baseline on Windows and Linux

Native Linux now uses the same available-memory headroom policy as native Windows: 1 GB minimum, 25% of available RAM up to 2 GB. With 8 GB installed and 4 GB available, both plan a 3 GB budget for the 0.8B model. This describes available RAM after OS/application usage, not a 4 GB installed-RAM guarantee.

The 2.5 GB smallest-profile minimum, 65% installed-RAM cap, 12 GB default ceiling, pre-load recheck and actual platform memory guards remain. Windows limits worker/model committed memory; Linux limits virtual address space per model process. Legacy Docker reserves are unchanged.

Both release platforms now gate publishing on source-mode real inference with simulated 8 GB total / at most 4 GB available and a real guard of at most 3 GB, in addition to packaged-model smoke tests. This does not establish physical low-end CPU compatibility or speed, whole-system peak memory, or universal task quality.

Use Fast for the smallest model; Balanced / Larger model can choose larger supported models on capable computers. Existing local data and learning features are preserved.
