# goproverbs session coordination

- Read [SESSION-HANDOFF.md](SESSION-HANDOFF.md) before editing or running
  experiments. The user reported overlapping work in two sessions.
- Check the ownership/status section and recent changes before choosing work.
  Record a bounded task and file scope when taking over; avoid another active
  session's scope. Prefer one implementation writer at a time in this checkout.
- The handoff is an advisory coordination record, not a filesystem lock. An
  absent owner entry is not proof that another session is idle.
- Preserve frozen snapshots, completed experiment directories and release ZIPs.
  Use new output directories for new runs. Do not repeat completed work merely
  because another session's conversation history is unavailable.
- Do not rebuild the executable used by a running match. Keep one inference
  workload at a time and follow the parent lab's VRAM/process instructions.
- On handoff, update the task status, changed files, validation and any running
  process/output location. Identify new evidence separately from old results.
