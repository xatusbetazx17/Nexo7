# Nexo 0.19 — your Navi over time

Open **Navi** after updating. Existing chat, documents, workspace, creation engines and read-only connections remain available. The new introduction appears until you name your Navi or choose **Maybe later** for the current browser session. It does not wait for model inference or enable a microphone, connector or avatar.

## Identity and continuity

Choose a name, how Nexo addresses you, a conversational style and a character mood. Names and preferences persist locally and travel in encrypted profile exports. The avatar displays the chosen name. The language model receives the chosen identity and relevant reviewed experiences within its existing context budget.

**Remember days with a completed conversation** is off initially. If enabled, Nexo records one generic activity per UTC day, without copying your question, answer, people or inferred emotions. Private chats and revoked memory-write permission prevent this recording. Activity dates expire according to your retention setting. The familiar/new labels describe recorded usage, not attachment, trustworthiness or feelings. They never grant permissions. An imported device asks you to enable activity recording again.

Character moods are user-selected presentation settings. Existing idle/listening/thinking/happy/sleeping avatar states describe application activity. Neither represents consciousness or real emotions. The assistant must not invent shared experiences, demand loyalty or use guilt.

## Experiences with a lifecycle

Under **Experiences worth remembering**, write what happened, when, and optionally with whom. Choose experience, decision or milestone. Edit mistakes, pin something important, or forget it. Maximum 500 experiences, 800 characters per description and 160 for people; retrieval supplies at most two relevant entries as untrusted reference data. Library documents and search caches retain their existing controls.

Unpinned memories expire after 90 days by default; choose 1–365 days. A changed default applies to new/edited memories and activity-date retention, not retroactively to every existing experience. Pinning keeps an experience until you delete it. Expired entries are excluded from retrieval immediately. Hourly maintenance while the desktop is running deletes expired unpinned entries and combines exact duplicate descriptions/people/categories from the same UTC day when older than 30 days. It adds occurrence counts rather than inventing a summary. Review cleanup manually from the same panel. Pinned entries and Library notes are untouched.

**Forget all experiences** also clears remembered active days. It invalidates the answer cache, but does not erase independent copies already in chat history, documents, exports, backups or other devices. Clear those separately if needed. Local SQLite storage is not a password-encrypted memory vault; the exported profile is encrypted. Episodes are not model-weight training or independently verified facts. Private chat omits episodic retrieval; chosen name/style preferences still apply.

## Graduated mail access

The progression is explicit: **Off → Local drafts only → Send with confirmation**. It never advances automatically through familiarity. Calendar remains read-only. This version supports plain-text email to one complete recipient address, without attachments, CC/BCC, message deletion or background sending.

1. Unlock the connector vault under Google connections. Choose **Local drafts only** in the draft panel. This requires no Google account connection and makes no network request.
2. Enter the From address of your connected Gmail account, the exact To address, subject and text. You can copy a generated reply into the draft. Up to five local draft records are stored in the encrypted vault, separate from Gmail's server-side Drafts folder.
3. To send, explicitly connect **Gmail · confirmed sending**. It requests only `gmail.send`, independently of the read connection. Follow the Desktop OAuth setup in NAVI-MODULES.md. Google still enforces the authenticated account's permitted sender identities. Check both From and To; Nexo does not resolve contacts or verify the person behind an address.
4. Choose **Send with confirmation**, save the draft and click **Review for sending**. The dialog shows the exact message. Press **Send this email** only after reviewing it.

Approval is single-use, expires after two minutes, and is bound to the stored message and permission state. Editing, locking through the UI, changing access level or starting a new preview invalidates the old approval. Revoking permission or disabling the connector blocks dispatch. The assistant, memories, incoming messages and chips cannot call a send tool; sending is a separate authenticated UI action.

Before dispatch the draft is marked delivery-unknown. A timeout, crash or ambiguous response never causes automatic retry. Check Gmail's Sent folder before composing another copy. A Gmail receipt marks it sent; this confirms API acceptance, not that the recipient read it. Local deletion does not delete Gmail messages. In-flight requests may finish after permission revocation or lock; dispatched email cannot be recalled by this application.

Tests cover MIME encoding, header injection, changed recipient/content, missing/expired/replayed approval, disabled permission/connector/vault and uncertain delivery. They use a fake Google transport; no real Google account was connected and no email was sent during development. Real account activation still requires your consent and may require Google app verification for public distribution.

## Mobile depth

The installable web app now carries the same name, persona and reviewed experiences through encrypted import/export. You can review, pin and forget imported experiences. Expired unpinned experiences and old activity dates are removed when unlocking. Notes can be shared through the device's own share sheet after explicit review. There is no automatic upload or synchronization.

Delivered reminders remain in an encrypted notification inbox after closing, locking or reloading. Mark them read or remove them. Clicking a browser notification opens **My day**. Notifications are still scheduled only while the app is open; overdue reminders are processed after unlock. There is no background push service or guarantee of delivery while the browser is suspended.

**Voice on this device** lists only voices the browser marks `localService`. Dictation is enabled only when the browser supports `SpeechRecognition.processLocally`, reports an installed on-device language pack and accepts local-only processing. The pack-install button may download a browser-managed pack once. Unsupported browsers show an explanation and never silently use cloud recognition. Dictation stops when backgrounded and places text in the composer for review, never automatic sending. Device speech availability and quality depend on browser/OS; physical iOS and Android speech have not been validated.

## Validation scope

The upgrade adds regression and adversarial checks for profile persistence, private mode, memory bounds/expiry, untrusted reference treatment, encrypted desktop/mobile transfer, draft approval races/replay and catalog integrity. Browser tests exercise named onboarding, saving an experience, offline catalog discovery, local encrypted drafts, notification persistence and actual offline model inference. Existing Windows/Linux release gates continue to run packaged avatar, TTS/STT, image generation, vision, language-model switching and simulated low-memory profiles.

These are engineering checks, not proof of factual accuracy, a clinical evaluation or a benchmark on your own PC/phone. Small models can still produce wrong answers. Long-term field testing needs real users and reviewed bug reports. True roaming, cross-service identity attestation, autonomous external writes, full mobile synchronization and background push are not implemented.
