# Third-party components

The MIT license covers Nexo's original code. It does not relicense external components.

- CPython and its standard library: Python Software Foundation License and included notices, https://docs.python.org/3/license.html. Portable binaries contain the interpreter and selected extension libraries.
- PyInstaller: GPL with its bootloader distribution exception, https://pyinstaller.org/en/stable/license.html. The exception permits bundled applications to keep their own license.
- SQLite: public domain, https://sqlite.org/copyright.html.
- OpenSSL, when included by the Python distribution: its applicable distribution license, https://www.openssl.org/source/license.html.
- Docker and Docker Desktop: their own licenses and subscription terms. Downloaded separately from official sources.
- Ollama: MIT licensed application, https://github.com/ollama/ollama. Model weights and container image dependencies retain their own licenses.
- Qwen3.5 model weights: consult the selected model's official license and model card before redistribution. Weights are downloaded separately and are not included in Nexo source or executable archives.
- PubMed records and linked papers: their respective rights and conditions. This project retrieves bounded records for the user's query; it does not redistribute full publications.
- PyTorch: optional educational experiment dependency; excluded from desktop builds.

Runtime license files available in the build environment are copied into the portable archive. Inspect them before redistributing a modified build with additional dependencies.

The optional cross-assembled Windows launcher uses Zig and mingw-w64 components. Their applicable notices are included in that archive's `licenses` folder. CPython's official Windows package includes its own `LICENSE.txt`.
