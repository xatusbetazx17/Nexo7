# Security notes

Nexo is an early local application. The browser API uses a random token, loopback binding and host/origin checks. Treat documents and model outputs as untrusted data; the UI displays their text without inserting user HTML. Model tools cannot execute shell commands, install software or write files without explicit user review/save.

The default model service is a native process running as the current user, with a random API key and OS-specific memory limits. It is not a filesystem/network security sandbox. Built-in llama agent, shell and MCP tools are disabled, and inherited llama/GGML configuration is removed. Engine/model downloads use pinned versions, exact sizes and SHA-256 checks; HTTPS redirects are allowed only during these catalog downloads. Do not expose either local server to a network.

Document extraction runs in a separate limited process with a timeout. It returns text for review and does not execute macros or embedded files. Scanned PDF OCR is not included. Workspace tools read only explicitly saved files; Python syntax checks do not execute code or prove it safe. Local notes/history/files are not encrypted. Local malware or an administrator can still access them and local services.

Legacy Docker mode remains for existing advanced configurations, with its separate local-daemon and cgroup checks. The desktop does not change Docker permissions or install drivers.

Do not publish secrets or personal chat data in bug reports. Use GitHub private vulnerability reporting when enabled; otherwise report reproducible issues with sanitized examples.
