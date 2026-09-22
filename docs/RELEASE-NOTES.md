# Nexo 7 0.6.1 — available-memory planning on Windows

Native Windows now reserves additional headroom from measured available RAM: at least 1 GB, 25% of available RAM up to 2 GB. With 8 GB installed and 4 GB available, the model budget is 3 GB, admitting the 0.8B profile. Windows already reports RAM available after OS/app usage. The previous extra 2 GB margin rejected this case.

The 2.5 GB smallest-profile minimum, OS process memory guard, 65% total-RAM cap, 12 GB default ceiling and pre-load resource recheck remain. Docker and Linux retain their prior reserve policy. Below 3.5 decimal GB available, this Windows configuration still declines to start. Diagnostics now show available RAM, headroom and resulting budget.

Windows CI also runs actual source-mode inference while simulating 8 GB total / at most 4 GB available and enforcing a real model-worker job limit of at most 3 GB. This is not a physical Dell/Pentium N5030 compatibility or performance test. Both packaged builds retain their native-model smoke tests.

Includes all 0.6 reviewed-learning features. No need to disable Windows services or remove memory guards.
