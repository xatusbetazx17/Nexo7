Nexo 7 v0.19.2 preview — comparison answers and reviewed-memory handling

- Comparisons receive compact guidance to define both terms, lead with the essential distinction and avoid fabricated differences. Spanish comparisons receive Spanish guidance, including common missing accents. Applies to desktop chat and text-only Telegram relay.
- General-knowledge questions no longer automatically echo an exact saved correction. Relevant saved corrections are still retrieved as untrusted references for the model. Personal exact-match shortcuts remain available.
- Learning UI explains that saving an example neither verifies its facts nor retrains the model. Existing notes are not rewritten or deleted.
- New answer-cache namespace avoids reusing replies generated under the previous prompt policy.
- Adds a real packaged-model regression for the user's Spanish chicken/hen comparison, alongside mocked routing/privacy tests and the existing Windows/Linux release checks.
- Preserves 0.19.1 Telegram chat selection and diagnostics and previous local features.

This is application-level prompting and routing, not new trained weights or an automatic fact checker. A small model can still make factual and reasoning mistakes; a single passed example does not establish general accuracy. Remove or correct erroneous saved learning examples yourself. Telegram account behavior still needs a live user check.
