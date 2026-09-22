# Release process

1. Update the version in `pyproject.toml`, `nexo7/__init__.py`, `desktop.py`, `server.py`, `scripts/build_desktop.py` and release notes.
2. Install requirements-runtime.txt, then run the unit suite and demo evaluation. Exercise the setup UI and test the packaged executable. Run scripts/smoke_native.py against the packaged app. Record GPU tests separately.
3. Commit all source and documentation changes to the public repository. Do not commit personal notes, chat databases, secrets, generated local configs, downloaded models or development build folders.
4. The first push to `main` automatically builds the v0.6.0 prerelease. For later releases, create a matching version tag on the tested commit and push it. The Desktop release workflow builds native Windows and Linux archives, smoke-tests them, and publishes a prerelease only when both jobs pass.
5. Inspect the Actions results and download each archive. Confirm its SHA-256 checksum and test installation on actual target machines before claiming broad compatibility.

The workflow uses the repository's ephemeral `GITHUB_TOKEN` with content-write permission only in the publish job. No personal token is stored in source. Manual workflow runs upload build artifacts but do not create releases. Existing releases are not overwritten automatically.

Optional Windows code signing and a full OS-native installer need additional release infrastructure. Current artifacts are portable executables with a browser-based setup interface.

## Cross-assembled Windows preview

`scripts/build_windows_portable.py` builds a Windows GUI launcher with Zig 0.15.2 and packages official CPython 3.14.7 from python.org. It verifies the pinned runtime archive hash and the launcher's PE machine/subsystem headers. These structural checks do not constitute Windows execution tests. The archive includes a visible preliminary-build notice and per-file hashes. Run `scripts/smoke_desktop.py` against the launcher on Windows before changing that status.
