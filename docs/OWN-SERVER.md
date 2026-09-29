# Run your own model server for Nexo 7

The built-in local models (0.8B–9B) are chosen to stay efficient on ordinary
hardware. When you want a bigger brain, you do not have to give your data to a
big AI company. Run the bigger model on a machine you control, and point Nexo 7
at it. Your questions go to your server, and nowhere else.

## What you need

- A machine that can run the model you want: your own PC, or a rented GPU box
  (vast.ai, runpod, and similar, a few cents per hour while it runs).
- Any server that speaks the OpenAI-compatible `/v1/chat/completions` API.
  Ollama and llama.cpp both do.

## Option A: Ollama on your own PC (free, stays in your house)

1. Install Ollama from https://ollama.com on the PC.
2. Pull a model that fits that PC, for example:
   - `ollama pull qwen2.5:7b` — comfortable on 16 GB RAM
   - `ollama pull qwen2.5:14b` — comfortable on 24 GB RAM
   - `ollama pull qwen2.5:32b` — needs about 20 GB free, fits a 24 GB machine
3. Make it listen on your home network (by default Ollama only listens on
   localhost). Set the environment variable before starting it:
   - Windows (PowerShell): `$env:OLLAMA_HOST="0.0.0.0:11434"`
   - Linux/macOS: `OLLAMA_HOST=0.0.0.0:11434 ollama serve`
4. Find the PC's home-network address (for example `192.168.1.20`).
5. In Nexo 7's `config.toml`:
   ```toml
   provider = "server"
   model = "qwen2.5:14b"
   server_url = "http://192.168.1.20:11434"
   ```
   Use the exact model name you pulled. Keep your PC awake while you chat.

## Option B: a rented GPU box (reachable from anywhere)

1. Rent a GPU machine and install Ollama on it, or use an Ollama template if
   the host offers one.
2. Expose it with `https://` (a reverse proxy with a free certificate, or a
   private tunnel such as Tailscale). Nexo 7 refuses plain `http://` for
   anything outside your home network, on purpose.
3. In `config.toml`:
   ```toml
   provider = "server"
   model = "qwen2.5:32b"
   server_url = "https://your-server.example.com"
   ```

## API key (optional)

If your server needs a key, never paste it into chat or into `config.toml`.
Set the environment variable before starting Nexo 7:

- Windows (PowerShell): `$env:NEXO_SERVER_API_KEY="your-key"`
- Linux/macOS: `NEXO_SERVER_API_KEY="your-key" ./nexo7`

## Efficiency notes

- The heavy work happens on the server. The device running Nexo 7 stays light:
  no big download, no hot phone, no drained battery.
- Pick the smallest model that answers well for you. A 7B or 14B is already a
  large step up from the on-device models; only reach for 30B+ models when the
  smaller one actually fails you.
- Quantized models (`Q4_K_M`) give the best quality per gigabyte. Prefer them.

## Safety notes

- `http://` servers are only accepted on your own machine or your private
  home network. Anything across the internet must use `https://`.
- Your server address and model name live in `config.toml`, which never leaves
  your computer. The key lives only in the environment.
- The same private-information guard that protects cloud requests also applies
  here: if your message looks like it contains a password, card number, or
  similar secret, Nexo 7 blocks the send before anything leaves.
