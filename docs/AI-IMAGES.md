# Offline AI image generation

Nexo 0.16 adds an optional diffusion engine alongside the existing chat model. LFM2-VL understands images; its weights have not been converted into an image generator. DreamShaper 8 LCM produces new raster images from text, including portraits, characters and scenes. Results can contain anatomical mistakes, inaccurate details and unreadable lettering.

## Desktop setup (Windows and Linux x86-64)

1. Install the 0.16 desktop release and open **Create → AI images**.
2. Choose **Download image model**. This explicit, one-time Internet download is approximately 1.64 GB. Keep at least 2 GB of disk space free. Pinned file sizes and SHA-256 hashes are checked before use.
3. Describe your image, choose a style, and select **Generate image**. English prompts work best. Generation itself works offline.
4. Download the PNG to keep it. Generated images are held in memory, not automatically saved in chat history or uploaded.

Once installed, **AI images for drawing requests** is enabled in chat. For example: “Draw a photograph of a fox in a sunlit forest.” Turn it off to use the existing simple PNG/SVG illustration path. Existing music and document tools remain available.

## Memory and speed

The desktop app temporarily unloads its owned native chat model, runs one image job, then tries to restore chat. Images use a separate, OS-limited CPU worker capped at 4 GB. Windows enforces committed memory; Linux enforces virtual address space. Nexo reserves 750 MB of currently available RAM outside that worker; file caches and total computer memory use are not capped by this setting.

- 256px draft requires at least 2.75 GB **available** after chat unloads.
- 512px requires at least 3.75 GB **available** after chat unloads.
- Choose 4 steps for speed or 8 steps for another quality/speed tradeoff. More steps do not guarantee a better picture.
- Cancel stops the worker. Jobs stop after 15 minutes. A low-memory failure suggests reducing resolution or closing other apps.

An 8 GB laptop with about 4 GB free may qualify, but its CPU speed still matters. A 4 GB installed machine may not have enough free RAM for diffusion. The Dell Pentium N5030 has not been physically benchmarked. Baseline builds do not require AVX/AVX2/BMI2; this release does not use GPU acceleration for images. Faster PCs can finish sooner, but this is not a performance guarantee.

## Components and licenses

- [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp), MIT, pinned commit in `nexo7/image_catalog.json`.
- [DreamShaper 8 LCM](https://huggingface.co/Lykon/dreamshaper-8-lcm), by Lykon, based on Stable Diffusion 1.5; CreativeML OpenRAIL-M. Nexo downloads the pinned [haven-ai-companion Q4 conversion](https://huggingface.co/haven-ai-companion/dreamshaper8-lcm-gguf).
- [TAESD](https://huggingface.co/madebyollin/taesd), by Ollin Boer Bohan, MIT. Its small decoder reduces memory use and may trade away detail.

License texts are bundled under `nexo7/licenses`; model use remains subject to the model license. The repository distributes application code and the runtime, not model weights.

## Building from source

Install Git, CMake and a C++ compiler (MSVC on Windows, GCC on Linux), plus the Python runtime requirements. Run `python scripts/build_image_runtime.py` before `python scripts/build_desktop.py`. The build pins the upstream engine and bundles a verified static CPU executable. The optional weights are downloaded through the desktop controls.

Release checks generate real 512px images on Windows and Linux, including a simulated 4 GB available-memory budget. Images and worker-limit receipts are retained as workflow review artifacts. These checks establish execution under the tested conditions, not universal prompt accuracy or laptop speed.
