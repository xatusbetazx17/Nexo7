# Everyday chat and what-if questions (v0.14)

## A simpler starting point

The sidebar now has **Chat**, **Create**, **Library**, and **Settings**. Light and
Dark appearance are available; the choice stays in this browser. Chat starts with
four suggestions and one question box. **Chat options** contains the response mode,
language, private-history option and search settings. Sources, usage counts and
feedback controls are under each answer's **Response details** disclosure.

**Allow online search for this message** is off by default and resets after sending.
Explicit **Search online** and **Search medical literature** modes also reset to
Automatic after one message. This avoids accidentally sending the next ordinary
question to Wikipedia. Search controls remain available in Chat options. Search
mode still means a search request; a no-results answer offers **Ask in conversation
instead**, so a failed source search is not silently passed off as verified knowledge.

The Create page has simple background-color, tempo and instrument controls. Drawing
and score JSON, the document editor and the project agent are expandable. Use
**Create file** on a valid drawing/score JSON response to place it in Creative Studio;
then create a preview. These are the same bounded renderers introduced in v0.13.

Settings puts the check/download/start steps first. Preferences, Telegram and setup
logs remain available below them. Saved examples and public contribution forms in
Library are also expandable. No permissions or sharing consent were removed.

## Imagined scenarios

Automatic detects common English/Spanish expressions such as **imagine**, **what if**,
**hypothetical**, **supongamos**, and **qué pasaría si**. It requests a discussion from the configured model
of the scenario, with assumptions and unknowns kept distinct. Fictional premises
should be distinguished from real physics. The prompt does not claim exact injuries,
collision damage or repair prices from an incomplete story.

These questions also leave explicit Web/Chat mode for scenario discussion unless the
message explicitly asks for an online search. Choosing **Imagine / what-if** manually
works for other languages or phrasings the heuristic does not recognize. With a local model configured, this discussion stays local. The text
model should use the requested response language, but language/reasoning quality
still depends on that model. There is no claim of new trained reasoning weights or
general accuracy. No online fallback is triggered merely because a hypothetical
answer expresses uncertainty. Ordinary local-model memory limits remain unchanged.

This is intent routing and prompting, not a full natural-language physics parser.
Numbers in a model-written answer are not automatically verified. For actual
calculation, use the explicit-input tool below.

## What-if calculator

Choose **What-if calculator** below the chat box. This tool needs no model or internet.
The displayed starting inputs are invented examples; replace them with your own.

- **Flight:** initial launch speed (m/s), launch angle (degrees), starting height (m).
  Calculates time to ground, horizontal distance and maximum height. Assumes a point
  object, constant gravity of 9.81 m/s², no air resistance and landing at height zero.
  Initial launch speed is supplied; it cannot be inferred from truck speed or a
  collision. This does not model injury or damage.
- **Cost:** paint area, paint rate, labor hours, hourly rate and other materials.
  Returns a decimal subtotal, rounded to two places, with the formula displayed.
  All inputs must use the same currency. This is not a current market quote; it
  excludes tax and unlisted work. Do not count labor/materials twice in your rates.

The authenticated `/api/scenario` endpoint accepts the corresponding JSON inputs.
The same calculation is available in chat with `/scenario` followed by JSON, e.g.:

```text
/scenario {"kind":"flight","speed_m_s":10,"angle_degrees":45,"height_m":0}
```

## Verification

Tests cover the user's scenario phrasing, EN/ES intent detection, no implicit web
fallback for hypothetical uncertainty, explicit search preservation, flight boundary
cases, decimal cost calculations and invalid inputs. UI checks cover collapsed
controls, one-message search, themes and calculator results. The release workflow
also captures real Chromium desktop/mobile screenshots and checks layout overflow,
keyboard chat, image previews and audio controls. Native-model smoke tests record a
hypothetical answer, but those checks establish routing/generation, not factual
correctness or a broad reasoning benchmark. The user's physical Dell is not tested.
