# Third-party components

The MIT license covers Nexo's original code. It does not relicense external components.

- CPython and its standard library: Python Software Foundation License and included notices, https://docs.python.org/3/license.html. Portable binaries contain the interpreter and selected extension libraries.
- PyInstaller: GPL with its bootloader distribution exception, https://pyinstaller.org/en/stable/license.html. The exception permits bundled applications to keep their own license.
- SQLite: public domain, https://sqlite.org/copyright.html.
- OpenSSL, when included by the Python distribution: its applicable distribution license, https://www.openssl.org/source/license.html.
- Docker and Docker Desktop (legacy optional path only): their own licenses and subscription terms. Downloaded separately from official sources.
- Ollama (legacy optional path only): MIT licensed application, https://github.com/ollama/ollama. Model weights and container image dependencies retain their own licenses.
- Qwen3.5 model weights: consult the selected model's official license and model card before redistribution. Weights are downloaded separately and are not included in Nexo source or executable archives.
- PubMed records and linked papers: their respective rights and conditions. This project retrieves bounded records for the user's query; it does not redistribute full publications.
- PyTorch: optional educational experiment dependency; excluded from desktop builds.

Runtime license files available in the build environment are copied into the portable archive. Inspect them before redistributing a modified build with additional dependencies.

The optional cross-assembled Windows launcher uses Zig and mingw-w64 components. Their applicable notices are included in that archive's `licenses` folder. CPython's official Windows package includes its own `LICENSE.txt`.

- llama.cpp b11093: MIT, https://github.com/ggml-org/llama.cpp/blob/b11093/LICENSE. Native archives are downloaded from the project's official release and verified using pinned SHA-256 digests. Archive notices are retained when extracted.
- pypdf 6.10.0: BSD-3-Clause, https://github.com/py-pdf/pypdf/blob/6.10.0/LICENSE. Bundled with desktop builds for text-based PDF extraction; license copied into the portable archive.
- GGUF conversions: bartowski/Qwen_Qwen3.5-{0.8B,2B,4B,9B}-GGUF on Hugging Face. Exact repository revisions, filenames, sizes and hashes are in nexo7/native_catalog.json. Model weights are separate downloads; consult the original Qwen Apache-2.0 terms and conversion repositories when redistributing them.
