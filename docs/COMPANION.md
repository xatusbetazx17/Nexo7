# Local companion: resource limits, personality and reviewed knowledge

Nexo7 0.10.0 adds practical companion features. It does not include new trained weights or demonstrated superiority over Siri, ChatGPT, Claude or all local models. A small model can generate inaccurate answers, even to simple questions. Successful engineering smoke tests do not establish factual accuracy.

## Memory and performance

The new native low-memory profile targets x86-64 Windows and glibc Linux machines with **4 decimal GB installed and at least 2.5 GB available at model startup**. Available RAM matters: a 4 GB computer running Windows and other apps may not meet that condition. Close apps and check again; setup refuses to launch when the measured budget is insufficient. Your 8 GB Dell with roughly 4 GB available still uses the existing profile.

The small profile uses the quantized Qwen3.5 0.8B model, a 4096-token context, shorter history, at most one model call per request and compact instructions. It leaves at least 1 GB of measured available memory outside the model-process budget. Batch sizes are bounded. The 4 GB release smoke test simulates 4 GB installed / 2.5 GB available and applies an actual 1.5 GB process guard. It is not a benchmark on a physical 4 GB PC or the Dell N5030.

Windows enforces a committed-memory Job Object limit for the worker and model; Linux enforces a virtual-address-space limit per model process. The desktop app, browser, OS, disk and dedicated VRAM are outside those guards. New native model calls are paused when the measured available RAM falls below 512 MB or cannot be measured. That check does not kill other applications, free the already-loaded model or guarantee that the whole PC cannot run out of memory during a request. Quit Nexo to unload it.

Larger supported models can be selected at the next setup/start when measured resources and performance preferences allow. Model selection is not an automatic live model upgrade or training operation. One local model is loaded; CPU threads remain bounded to preserve responsiveness. The existing 16 GB absolute configuration ceiling remains, with conservative setup budgets capped at 12 GB. Calculators, notes and document export do not need the language model. Voice, arbitrary app automation and unlimited background agents are not added in this release.

## Personality

In Setup, choose calm/direct, friendly, patient coach or lightly playful. Optionally enable responding to the tone you explicitly express. Preferences persist locally and invalidate answer caches. Prompt instructions keep facts, uncertainty and permissions separate from personality and ask the assistant to remain respectful when insulted.

This simulates an expressive conversational style; it is not real feeling, consciousness or proof of empathy. It does not form hidden emotional profiles, grant actions, infer diagnoses or authorize sharing. The small model can fail to follow these instructions; personality is not a security boundary.

## Reviewed knowledge

Saved web excerpts remain dated, unverified source material. To create a separate reviewed local note:

1. Open My knowledge → Saved web sources → **Review for local learning**.
2. Examine the original source, its date, relevant evidence and any conflicting claims. Write the question and a corrected answer in the learning editor.
3. Check the review box and save the exact example. Editing clears consent.

The note retains its source URL, retrieval time, expiry and review time. It is labeled user-reviewed, not independently verified. Source-linked notes enter model context as reference data; they are not returned as unquestioned exact answers. After source expiry they remain visible but are excluded from automatic retrieval. Refresh the source, select it again and explicitly re-review/save the example to renew it. If the same example already exists without that source link, explicitly review and remove the old example before replacing it.

The older portable learning-pack format cannot carry source provenance/expiry, so it refuses to export these notes. The **Contribute a note** flow on saved sources remains the path for voluntary public GitHub submissions with original wording and separate rights/privacy consent. See [Contributions](CONTRIBUTIONS.md). Local review does not grant publication rights. No note automatically uploads, trains weights or promotes a model version. Maintainers still need reviewed data and independent evaluation for actual weight updates.

## Privacy and online requests

Before a new Wikipedia/Brave/PubMed query or a cloud-model request, a conservative screen blocks recognizable email addresses, credential patterns, long personal-number patterns and personal file paths. It does not send the blocked text and does not silently redact it into a different question. Use a general topic without the flagged information. Native offline text processing does not apply this outbound restriction.

These patterns have false positives and miss some private information, such as names or identifiers without recognizable formatting. Review your queries. Online services receive the searches you approve; the optional cloud provider receives its conversation/context. The saved local database is not encrypted. Private chat avoids saving new history, but does not make an explicitly requested online operation offline. These controls reduce exposure; they cannot guarantee freedom from harm or information leaks in all circumstances.

## Word documents

Ask for document text, choose **Create file**, then review/edit it in My workspace. Set the document title and choose **Download reviewed text as Word (.docx)**. You can also write the text directly without a model.

The export is local and macro-free. It preserves Unicode text and turns Markdown #, ## and ### headings into Word heading styles. It does not embed remote links, images or scripts. The result uses US Letter pages with one-inch margins. Complex tables, images, pagination fidelity and full Markdown formatting are not supported; inspect layout in Word or LibreOffice before sharing. Saving the editable text in the workspace is a separate action.
