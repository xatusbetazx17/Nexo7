# Shared knowledge and offline calculations

## Contribute an original note

1. In My knowledge, expand Saved web sources and select **Contribute a note**.
2. Write a question and your own answer, choose its language, and explain why you own the rights to your wording. Do not paste the saved excerpt or paraphrase protected text just to bypass the copied-text screen.
3. Review the rights, private-data and public CC0/training declarations. Check each box only if it is true for the exact note.
4. Select **Prepare contribution** and read the complete JSON and declaration shown locally. You can download the JSON without uploading anything.
5. Select **Open GitHub draft to review and submit**. Opening this link sends the draft to GitHub. Sign in with your own GitHub account and submit the issue to publish it. Nexo7 never needs your GitHub password or token.

Editing the note resets consent. The payload contains your question, answer, language, reference URL (without query or fragment), source retrieval date, rights statement and consent. It does not automatically include the saved excerpt, conversations, computer details or other notes. Review the reference URL too: its path can itself contain private information.

Only original notes whose rights you control are supported by this submission format. The CC0 declaration covers your contribution, not the referenced webpage. Public access to a webpage is not permission to republish it. Copied-passage and private-data screens are limited heuristics; passing them does not prove ownership, privacy or truth. Do not submit personal, confidential, employer-owned or third-party material without the necessary authority. Published material can be copied and persist even after an issue is deleted.

Background: [US Copyright Office: what copyright protects](https://www.copyright.gov/help/faq/faq-protect.html), [Creative Commons licensing considerations](https://creativecommons.org/share-your-work/licensing-considerations/version4/). Applicable rights depend on the material and jurisdiction; the software does not make a legal determination.

## Maintainer admission to training

An issue is a proposal, not approved training data. A maintainer must check ownership/permissions, privacy, factual support, source date, malicious instructions, usefulness and duplicates. Reject questionable material. A reference alone is not factual verification, and source retrieval time is not the date a claim became true.

Save the exact JSON object from each accepted issue as a separate file. Do not edit it: its content hash detects changes. Record your review in a JSON file keyed by the contribution's full `id`:

```json
{
  "FULL_CONTRIBUTION_ID": {
    "rights_checked": true,
    "privacy_checked": true,
    "facts_checked": true,
    "approved": true,
    "reviewer": "maintainer-handle",
    "reason": "Describe the permission and evidence actually checked."
  }
}
```

Convert only accepted submissions into a new training-only JSONL file:

```sh
python -m research.contributions note-one.json note-two.json --reviews reviews.json --output approved-train.jsonl
```

The converter checks hashes, explicit decisions, supported declarations, duplicates and possible private data. It validates the entire batch before creating the output. Review booleans are a record of human work, not independent verification. Files from the same reference URL receive the same dataset group. Related URLs, translations and paraphrases still need manual grouping and leakage review.

Combine these training rows with separately curated validation and test groups, then use the [model improvement workflow](MODEL-RESEARCH.md) to prepare, train, evaluate and compare a candidate. Do not put these training examples in the held-out evaluation set. Keep contribution and review records for provenance. Only release a candidate after measured quality, regression and memory checks on the target hardware. No training or weight replacement happens when somebody submits an issue. Training is a separate maintainer job that can need much more memory than desktop inference.

## Offline math

The chat screen has an **Offline math** panel for:

- Quadratic equations: `1, -5, 6` represents x² − 5x + 6 = 0, with roots 2 and 3. Complex roots are supported.
- Linear systems: one matrix row per line and a separate right-hand vector, up to 8 equations in 8 unknowns. Singular systems are rejected.
- Statistics: up to 500 values, with sum, mean, population variance and population standard deviation.

These tools compute locally with 50-digit Decimal arithmetic and use no model tokens or Internet requests. Values are rounded; a small substitution residual is not a guarantee of accuracy for an ill-conditioned system. Inputs are bounded to finite numbers of at most 100 characters, magnitude at most 1e50 and decimal exponent at least -50. Use decimal strings in JSON to preserve input precision.

The same operations are available from chat:

```text
/math {"operation":"quadratic","a":"1","b":"-5","c":"6"}
/math {"operation":"linear","matrix":[["2","1"],["1","-1"]],"vector":["5","1"]}
/math {"operation":"statistics","values":["0.1","0.2","0.3"]}
/calc sin(pi / 2)
calculate sqrt(144)
```

The scientific `/calc` functions use ordinary floating-point arithmetic, and trigonometric functions use radians. These bounded calculators are not a general symbolic mathematics engine. Arbitrary word problems still depend on the model selecting the correct formulation; check assumptions and units.

## What improves, and what does not

Ordinary local chat uses the downloaded model's existing knowledge. Internet access is optional for Companion requests; saved searches and approved local examples can supplement that knowledge. Those mechanisms do not automatically retrain the model. This release adds a path from voluntary notes to reviewed training data, not new trained weights, knowledge of the whole Internet or demonstrated parity with ChatGPT, Claude or other large assistants.
