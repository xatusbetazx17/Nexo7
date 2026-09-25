# Create directly in chat (v0.15)

In Automatic chat, try **Draw me a chicken**, **Draw me a hand**, **Draw a red ball**, **Create a Word document with a thank-you letter**, or **Make a short melody**. Spanish drawing/document requests are also recognized. Explicit `/draw`, `/document` and `/music` prefixes are available when automatic routing does not recognize your phrasing.

Drawings show a PNG preview and PNG/SVG download links. Music shows a WAV player and WAV/MIDI links. Documents return Word-compatible DOCX and plain text. You can also choose **Download Word** on a normal completed chat reply. This does not add native Excel, PowerPoint or PDF generation.

The chicken and hand examples are hand-authored built-in illustrations, labeled as such. Other drawings and scores are drafted by your selected model and validated before rendering. Small models can produce poor designs or invalid JSON; Nexo reports a failure when validation fails. No second model, image-generation weights or GPU is loaded. Model quality and resource limits still apply. Word content is a draft and needs review.

Files are generated in memory and are not automatically saved or uploaded. **Download before leaving or reloading the conversation**; history retains text, not the binary attachments. Rendering and DOCX export work offline; drafting uses your configured provider (a remote provider still sends the prompt to that provider).

The advanced editor below remains available for manual control.

# Creative Studio

Open **My workspace → Creative Studio** in the desktop app on Windows or Linux.
Choose Drawing or Music, then **Render and preview** to try the supplied example.
Download links save actual PNG/SVG images or WAV/MIDI music files. Music plays only
when you press the audio player's Play button. Rendering is offline and does not
require a model, GPU, account, extra weight download or tokens.

## Create your own

Edit the JSON example, or describe an idea and choose **Ask chat to draft an editable
design**. This fills the normal chat composer; review and send it. When the model
answers, choose **Create file**, then **Use JSON from file editor** in Creative Studio.
Review the drawing/score and render it. You can also paste JSON directly. Save its
text as a `.json` workspace file if you want to edit it later.

Chat drafting uses your configured chat provider and normal chat settings. The
renderer itself never contacts a provider. To draft offline, use a local model and
keep optional web research off. Small models can produce invalid JSON, poor images,
or weak compositions; renderer errors identify unsupported input, but do not repair
it automatically. A working example is always available through **Reset example**.

## Drawings

A drawing is a JSON object with `width`, `height`, `background`, and `shapes`:

```json
{"width":512,"height":512,"background":"#8ed6ff","shapes":[
  {"type":"ellipse","box":[100,150,400,350],"color":"#ffffff"},
  {"type":"text","x":140,"y":220,"size":24,"color":"#223344","text":"Hello!"}
]}
```

Canvas: 64–1024 pixels per side. At most 128 shapes. Colors use `#RRGGBB`.
`rect` and `ellipse` use `box:[x1,y1,x2,y2]`. `line` also supports `stroke` 1–32.
Coordinates are integers inside the canvas. `text` uses x/y, size 8–72 and at most
120 characters. PNG uses the bundled default font; glyph coverage is limited.
SVG may use different fonts on your computer, so text placement can differ.

Only these shapes are rendered. No scripts, external images, URLs or HTML are
executed. SVG text is escaped and only PNG is displayed in the app preview.
This is simple illustration and vector graphics, not diffusion or photorealistic
generation. Image understanding remains a separate optional LiquidAI feature.

## Music

```json
{"bpm":110,"instrument":"soft","notes":[
  {"pitch":60,"start":0,"duration":1,"velocity":80},
  {"pitch":64,"start":1,"duration":1,"velocity":80},
  {"pitch":67,"start":2,"duration":2,"velocity":80}
]}
```

`bpm`: integer 40–240. `instrument`: `soft`, `bell`, or `synth`.
`pitch`: integer MIDI note 36–96 (60 is middle C).
`start` and `duration` are beats; duration is 0.125–8 beats.
`velocity`: integer 1–127, default 80. Use simultaneous starts for chords and gaps
for rests. Maximum 256 notes, eight simultaneous voices and 30 seconds total.
Overlapping notes of the same pitch are rejected to keep MIDI playback unambiguous.

WAV is synthesized mono 16 kHz PCM, with attack/release envelopes and peak
normalization. MIDI retains notes, timing, velocity and an approximate General MIDI
instrument selection; its sound depends on the player/sound bank. It is editable in
a MIDI sequencer. These are synthesized instruments, not vocals, realistic recordings,
a licensed sample library, or a text-to-song neural model.

## Resources, privacy and testing

One creative render runs at a time. Drawing dimensions, note count, polyphony and
song duration bound computation and allocations. The renderer uses no model calls
and does not alter the existing model's memory guard. The app/browser/OS still need
memory; this is not a guarantee about total PC RAM or speed on every 4 GB computer.

Generated binaries stay in browser memory until explicitly downloaded. Replacing
the preview releases its browser URLs. No creative data is uploaded, trained on,
or contributed to GitHub automatically. Existing chat-history settings still apply
to prompts you send to chat. Downloading an SVG/MIDI is not automatic execution.

Automated checks cover actual PNG pixels, inert SVG text, WAV duration/amplitude,
MIDI structure, resource limits, authenticated API access and browser UI events.
Desktop packaging smoke tests render PNG, WAV and MIDI through the real executable
on both Windows and Linux. These are functional tests, not an artistic quality
benchmark or a physical test on the user's Dell.
