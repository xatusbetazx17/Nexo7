# Answer quality investigation — 2026-09-27

Version 0.19.2 is a development candidate, not a published fix for general knowledge.
The Windows/Linux release gate includes the user's Spanish comparison question and must remain blocked until the actual answer is correct.

## Implemented application changes

- Exact Spanish/English greetings receive a built-in social reply without inference or network access, in desktop chat/companion and text-only Telegram relay. Greetings with an appended task are not intercepted. Explicit unsupported response languages continue to the model.
- Common general-knowledge questions no longer reuse an exact reviewed answer verbatim without inference. The reference still reaches the model, so this is not a fact checker and cannot guarantee correction of bad notes.
- Generic comparison guidance is shared by desktop and relay. It is insufficient to repair missing knowledge.
- Saved notes are not rewritten. Incorrect corrections must be edited or removed by the user.

## Real CPU observations

Pinned models and runtime are in `nexo7/native_catalog.json`. The input was `cual es la diferencia entre un pollo una gallina`, with a short Spanish system instruction. No online sources or factual hints were supplied.

| Model | Observed problem |
| --- | --- |
| Qwen3.5 0.8B Q4_K_M | Invented feeding/housing differences; packaged app regression also invented color/size differences. |
| Qwen2.5 1.5B Instruct Q4_K_M | Repeated a circular explanation. English chicken/hen comparison was substantially better, but Spanish definitions still contained errors. |
| Qwen3.5 2B Q4_K_M | Loaded and replied under an enforced 2.7 GB Linux process virtual-address limit, but described pollo as male and asserted that it lays eggs. Not a valid upgrade for this case. This does not measure whole-PC RAM or establish Windows/Dell performance. |

Enabling thinking on 0.8B with a 512-token output cap produced no final answer in three probes. The model-card sampling configuration also produced incorrect comparisons. Neither experimental setting was adopted. The 2B experiment does not change production memory admission limits or defaults.

The factual distinction required here: gallina is an adult female; pollo commonly refers to a young bird or its meat, depending on context. Diet, feather color and free-range housing do not define this distinction.

## Remaining acceptance work

Evaluate a genuinely stronger multilingual checkpoint or an independently sourced offline reference system across multiple unrelated facts, not just this example. Keep existing resource guards. Test greetings, task routing, factual definitions and comparisons through the packaged Windows/Linux API. Do not relabel keyword matches as verified factual correctness or remove the failing regression to publish.

Primary sampling reference: https://huggingface.co/Qwen/Qwen3.5-0.8B
