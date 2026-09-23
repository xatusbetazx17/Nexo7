# Persistent workspace tasks

Open **My workspace → Build a project, one checked step at a time**.
Enter your goal. **Suggest steps from my goal** asks the local model for a draft;
inspect and edit the plan before saving. You can also enter steps yourself:

```text
square.py | Define square(n) returning n*n | def square | [{"function":"square","args":[3],"expected":9},{"function":"square","args":[-4],"expected":16}]
README.md | Explain how to use square.py in one sentence | square.py
```

Each line is `filename | instruction | optional required text | optional Python test JSON`.
Separate multiple required text checks with `;;`. Up to four different target files
are supported. Existing workspace files are edited; other files are created. This
version uses the app-managed workspace, not arbitrary project folders.

1. Save the plan. Its goal, steps and history persist across restarts.
2. Generate the next step. Nexo reads the target and bounded excerpts of prior
   verified task files, generates a proposal, and checks it. If a check fails, it
   can make one correction within its call budget. On the smallest profile,
   press Resume for the second attempt because each request permits one call.
3. Inspect the complete proposal and line diff. **Apply reviewed change** applies
   only that exact proposal. A file modified since generation is rejected.
4. The saved content is read back and checked. The next step becomes ready.
   Generate it when ready. Only after all steps are applied does the task show
   completed. Review pauses do not consume model time.
5. **Undo last applied step** restores the previous content, or removes a newly
   created file, provided nobody changed it afterward. Undo cancels the plan;
   you may undo earlier applied steps in reverse order too.

A task is completed with respect to its declared checks, not a proof of general
correctness. Python syntax, JSON parsing, CSV structure and required text are
checked. Optional Python cases use a small AST interpreter for single-return
scalar arithmetic/comparisons/conditional expressions, with no exec/eval,
imports, calls, loops, file access or network. Unsupported programs fail these
checks rather than running. This is not a substitute for full project tests,
application execution or a security audit. General text also needs human review.

## Limits and persistence

- Local native/Ollama providers only. File contents are never sent to a cloud
  provider by the task engine. Search remains a separate, explicit feature.
- Four steps, two generation attempts per step, 4,096 reserved output tokens
  per task, and existing per-request context/output/model-call limits.
- A 600-second accumulated active-time threshold prevents another inference
  from starting; an already-started call can consume its configured timeout
  (up to 180 seconds). There is no endless retry loop.
- Maximum 8 KB target/proposed file, 50 saved tasks, bounded history and excerpts.
  The original workspace file/count quota and process memory guards still apply. Native runtime prompt caching and recurrent context checkpoints are disabled to avoid the runtime defaults growing during longer task sequences.
- The Cancel button works between bounded requests. It does not force-kill an
  active inference. Applied files remain until explicitly undone/deleted.
- Interrupted generation becomes blocked on restart. Interrupted application
  requires inspecting the before/proposed snapshots and actual files, then a
  new plan; it cannot silently resume and declare success.
- Task history contains goals, file contents and rollback snapshots, stored
  locally without encryption. Delete task history to remove those records;
  applied workspace files are separate. Private chat does not disable explicit
  task saving. Nothing automatically becomes a learning example or GitHub post.

## Model comparison and optional candidate

A small diagnostic compared Qwen3.5 0.8B, Qwen3.5 2B and Qwen2.5 1.5B Instruct
under the same real 3 GB process limit, 4096 context, CPU execution and 128-token
answer cap. Prompts, raw responses and timings are in the three
`reports/quality-*.json` files. Reproduce one with:

```sh
python scripts/evaluate_quality.py --model qwen2.5:1.5b --data-dir /tmp/nexo-quality --output reports/my-quality.json
```

On Windows choose a suitable local `--data-dir` instead. This command downloads
verified weights and measures hardware before admitting the requested memory
budget. It runs one model at a time; no generated Python is executed.

Eight cases have automatic checks: two deductions, two arithmetic word problems,
uncertainty for a fictional planet, JSON formatting, one simple function and an
exact-format instruction. The two definitions require human review. Keyword
presence was found to overrate incorrect definitions and is no longer scored.

| Model | Automatic cases passed | Review of the two definitions |
|---|---:|---|
| Qwen3.5 0.8B | 6/8 | English usable; Spanish contains false details |
| Qwen3.5 2B | 6/8 | English repetitive; Spanish contains false details |
| Qwen2.5 1.5B Instruct | 5/8 | Both simple definitions usable in this diagnostic |

All three failed both arithmetic word problems without tools. The candidate
missed the exact-format instruction. In the separate app smoke test, it also
added a misleading "typically a female" phrase to an English chicken definition.
Thus it is an **optional tradeoff, not a universally better model**, and the
existing default is unchanged. Ten prompts and a single run are not a broad
benchmark, do not cover robust programming, and do not establish performance
on the Dell N5030. Timing numbers are from the test host, not that Dell.

To try the candidate: Setup → Local model choice → **Qwen2.5 1.5B chat candidate**,
save preferences, then restart local setup. It needs at least a 3 GB model budget
plus host headroom (normally 4 GB available). The minimum-memory 4 GB installed /
2.5 GB available profile retains Qwen3.5 0.8B. Both use the existing bounded
native runtime; the candidate does not bypass memory checks.

The next quality milestone is a larger, independently reviewed held-out suite
and reliable tool selection for word problems—not a claim that larger downloads
or more agent loops automatically make answers correct.
