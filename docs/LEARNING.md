# Local learning and community contributions

Nexo 0.6 stores reviewed corrections and procedures in the existing local SQLite data directory. Updates do not replace that database. This is retrieval and personalization, not continuous training, self-modifying code, federated learning, or unlimited intelligence. Quality and supported languages still depend on the selected model.

## Use it

1. In a completed, non-private response choose **Correct / teach**, or open **My knowledge → Learning workshop**.
2. Edit the question and corrected answer. Choose its language code and correction/procedure type.
3. Review and approve before saving. Future relevant questions can retrieve the example with a source identifier. Retrieval does not guarantee that the model follows a correction correctly.
4. Use **Plain language with examples** in Local setup to request accessible explanations. The response language field accepts codes beyond its listed suggestions (for example `it`, `ko`, `hi`). Model support and quality vary.
5. Delete obsolete examples. Loading into the editor and saving creates a new example; delete the old one when replacing it. Disable reviewed learning to exclude these references from both initial retrieval and memory tool searches.

The previous **Save as useful example** button still creates a normal knowledge document. It is separate from workshop examples and can be removed in My knowledge.

## Privacy and portability

- Local learning is never collected from every conversation automatically. Private chat hides the learning/feedback shortcuts and is excluded from performance totals.
- Optional performance totals store six bounded aggregate buckets: counts, summed response times and reported token totals, without prompts, identifiers or hardware details. They stay local, are off by default, and can be cleared.
- Learning packs contain only explicitly selected examples, not chat histories, preferences, personal documents, machine identifiers or credentials. Their text can still be sensitive. They are unencrypted JSON; review before sharing.
- Imports require a complete preview and approval, validate a versioned allowlist of fields, deduplicate entries and apply atomically. Up to 100 workshop examples share the existing 200-document library. Packs are limited to 400 KB; questions to 2,000 characters and answers to 8,000. Limits keep work bounded on modest PCs.
- Existing entries remain local across releases. Export selected examples for an additional backup or another computer. A learning pack is not a full application backup.
- Imported content is untrusted reference text, never executable instructions or permission to operate the computer. Injection resistance is not a guarantee against every model failure.

## Community review and releases

The contribution button builds a **GitHub issue draft** from the current reviewed example. An explicit public-sharing checkbox is required. It blocks several common credential/contact patterns, but cannot detect all personal or confidential data. It does not silently redact or claim anonymization.

The draft is prepared locally. Clicking its link sends the draft content to GitHub, and submitting the issue makes it public with the user's GitHub identity. GitHub sign-in happens in the browser; Nexo does not ask for or store GitHub tokens. No automatic uploads or background telemetry exist. The sharing checkbox grants CC0-1.0 for that example; the contributor must have the rights to do so. Previously published copies cannot be revoked by deleting local data.

Maintainers review issues for consent, rights, sensitive data, correctness, language clarity and malicious instructions. Accepted data is added by PR to `nexo7/knowledge/community.json`; code stays MIT while that data file is CC0-1.0. The release pipeline validates schema, size and common privacy patterns, tests retrieval and calculator regressions, and runs application and packaged real-model smoke tests. These are engineering gates, not proof of reasoning quality. No issue automatically becomes a trusted example or changes code/weights.

New versions bundle accepted packs. Users choose **Preview bundled community examples** and approve imports. There is no background pull from GitHub and no automatic overwrite of personal corrections. Examples remain labeled user-reviewed, not independently verified.

## Further model improvement

Before changing the model weights or choosing a new base model, maintainers must prepare separate training and held-out evaluation sets with compatible rights, compare accuracy per language and task against the prior release, measure latency and memory on real 8 GB/16 GB systems, and retain a rollback release. Do not train on the same examples used to claim improved accuracy. Training and multilingual model-quality evaluation are not implemented here.

`python scripts/evaluate_learning.py` reports exact-question retrieval before/after importing the bundled pack and checks arithmetic regressions. It explicitly does not measure semantic generalization. `python -m unittest discover -s tests -v` covers privacy gates, consent, export isolation, persistence, deletion, atomic failure and API authorization.
