# Chip discovery and sharing

Navi → **Discover and share chips** lists the release's curated catalog without making a network request. Built-in math, reviewed web-memory and security-watch chips are already installed. The optional **study-math** sample demonstrates remote distribution of the existing math operation; it is not an additional model or a new mathematical solver.

**Download and inspect** contacts only the release-pinned project URL listed in `nexo7/chip-discovery.json`. The download is capped at 100 KB and must match both SHA-256 and publisher fingerprint. Its ZIP and Ed25519 signature are validated before a preview is returned. Installing requires a separate review action and the install permission. Running an installed chip separately requires its execution and declared operation permissions. Discovery does not activate a chip.

A publisher fingerprint identifies a key, not a verified person. The interpreter still accepts only `math.solve`, `memory.reviewed-save` and `security.email-check`. No arbitrary Python, JavaScript, shell, filesystem access or chip-provided network address is accepted. There are no payments or automatic catalog updates. A later application release can change the curated list.

Use **Download signed chip to share** on an installed catalog item, or the existing local-file workflow for other chips. The downloaded archive includes the public signature, not your Navi private key. You decide where to share it. Do not package personal data, credentials or third-party material you cannot redistribute.

To propose a catalog entry:

1. Follow the authoring command and manifest format in [NAVI-MODULES.md](NAVI-MODULES.md).
2. Test the chip locally with permissions revoked and enabled. Keep the signing key private.
3. Open a pull request to this repository with the `.nexochip`, publisher fingerprint, SHA-256, description, declared permissions, source/license and test evidence.
4. A maintainer reviews it and pins its release URL/hash in `chip-discovery.json`. Submission is not automatic installation or an endorsement of the author.

The example's signing seed was generated for packaging and was not stored in the repository. Its signed package and fingerprint are retained. A new key would produce a different publisher fingerprint and requires review.
