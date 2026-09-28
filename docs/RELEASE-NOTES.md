Nexo 7 v0.19.2 preview — Telegram, browser companion and appearance

**Known unresolved limitation:** the real Spanish comparison diagnostic fails. This release does not fix general model accuracy. Accuracy results are uploaded as model-answer-review artifacts and the failed diagnostic remains visible in CI; required application, privacy and memory tests still block publication. See docs/ANSWER-QUALITY-STATUS.md.

- Telegram adds model-independent `/ping` and `/start`, authenticated bot username, last successful polling time and actionable blocked-chat diagnostics. No live bot was connected during development.
- Optional private-Wi-Fi browser companion for Mac/iPhone/iPad, independent revocable key, no app installation on the client, no admin/file/email access. HTTP only: trusted network and non-sensitive use.
- Five accent palettes/custom color plus robot/cat/orb avatar appearance. See BROWSER-COMPANION.md.
- Exact English/Spanish greetings now use a bounded local social reply in desktop and Telegram text relay. No model or web request; mixed greeting-plus-task prompts still reach the model. This is routing, not learned reasoning.
- Comparisons receive compact guidance to define both terms, lead with the essential distinction and avoid fabricated differences. Spanish comparisons receive Spanish guidance, including common missing accents. Applies to desktop chat and text-only Telegram relay.
- General-knowledge questions no longer automatically echo an exact saved correction. Relevant saved corrections are still retrieved as untrusted references for the model. Personal exact-match shortcuts remain available.
- Learning UI explains that saving an example neither verifies its facts nor retrains the model. Existing notes are not rewritten or deleted.
- New answer-cache namespace avoids reusing replies generated under the previous prompt policy.
- Adds a real packaged-model regression for the user's Spanish chicken/hen comparison, alongside mocked routing/privacy tests and the existing Windows/Linux release checks.
- Preserves 0.19.1 Telegram chat selection and diagnostics and previous local features.

This is application-level prompting and routing, not new trained weights or an automatic fact checker. A small model can still make factual and reasoning mistakes; a single passed example does not establish general accuracy. Remove or correct erroneous saved learning examples yourself. Telegram account behavior still needs a live user check.
