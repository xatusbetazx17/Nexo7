# Nexo7 Companion — 0.8.0

Companion is a bounded local assistant workflow, not a new foundation model or an
unrestricted autonomous agent. It uses the existing small model and memory guards.
No extra embedding model, background trainer or always-running researcher is loaded.

## Everyday use

Choose Companion, type your request, and send. Familiar questions use the compact
Chat path. Requests for saved knowledge or matching reviewed examples use local
retrieval. An exact reviewed question in a compatible response language can reuse
the saved answer with **zero model calls**. Disable reviewed learning in preferences
or delete the example to stop reuse. Reuse is not independent fact checking.
Conversation history and the existing response-language/style settings remain local.

Use Correct / teach to edit and approve an answer or useful procedure. Nothing is
silently promoted from a generated answer or search excerpt into reviewed learning.
Existing export/delete controls apply. Model weight training remains a separate,
explicit research workflow; everyday learning here means reviewed memory.

## Research

Enable **Allow Internet research for this request** when you want Companion to
research. The checkbox resets after every request and New chat. The selected search
provider receives the question. It does not receive imported workspace-file contents
through the repair path. Wikipedia needs no key; Brave needs your key and appropriate
storage rights, as described in WEB-RESEARCH.md. Remember web excerpts remains a
separate explicit option. Private mode does not save new excerpts or conversation.

Freshness/search signals choose research immediately. When a local answer explicitly
expresses uncertainty, Companion may perform **one** web follow-up if permissions,
model-call and token budgets allow. It does not reliably know everything it does not
know: a confidently wrong answer may not trigger research. Routing and uncertainty
patterns currently cover selected English/Spanish phrases, not all languages.
Other languages can use explicit Web lookup. It never loops until it invents success.

The visible request steps explain the chosen route. The evidence panel reports source
URLs, retrieval/expiry dates and distinct hostnames. The model is instructed to favor
identifiable original sources and state disagreements. **No automatic factual truth,
entailment, publication-date verification or source-independence guarantee is made.**
Wikipedia results can all originate from one site; different domains may repeat the
same claim. Cached excerpts follow the existing seven-day reuse policy. Review the
linked originals for important decisions; no arbitrary full-page browser is included.

## Device and files

- `/device`, `check my computer`, or `revisa mi pc`: read OS, RAM and CPU-thread
  observations without a model call. This does not diagnose every fault or repair OS settings.
- `/inspect filename`: inspect an existing workspace artifact using deterministic
  JSON/Python syntax checks, CSV statistics or text counts.
- Create file: review generated content, give it a name and save. The saved artifact
  is inspected immediately and the result is displayed. Invalid syntax remains a
  visible failed check; it is never presented as a working program.
- `/repair filename.py` or `/repair filename.json`: inspect the original. If syntax
  fails and the file is at most 2,500 characters, request one local model repair
  proposal. The workspace also has a Propose syntax repair button. Review Create
  file, save a new candidate, and inspect its new check. No original is overwritten.
  A valid-syntax file gets no speculative repair. Larger files require a smaller
  failing example. Python syntax validity is not execution, security or behavior validation.
- Ask about file selects the existing tool-enabled mode explicitly.

Generated code is never executed. There is no automatic installation, system-file
editing, purchasing, messaging, credential use or unrestricted filesystem access.
Destructive workspace deletion retains its explicit confirmation. Do not confuse a
repair proposal or metadata check with a successfully tested real-world outcome.

## Resource and release scope

Companion performs at most two generation calls for the uncertainty/research path,
and never exceeds the configured model-call cap. Each call shares the existing model;
there is no second resident model. Basic native replies remain capped at 128 tokens.
File proposals and source summaries use the configured output allowance. It can still
be slow or wrong on a modest CPU. The Dell N5030 has not been directly benchmarked.

This connects the existing application features into a practical first companion.
General autonomous troubleshooting, robust fact checking, full multilingual intent
recognition, arbitrary app control and demonstrably improved model intelligence
remain future work. The small model's limitations have not disappeared.
