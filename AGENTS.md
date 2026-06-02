# Baseline Evaluator v0 Orchestration Anchor

This repository currently has an active orchestrated task managed through:

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- `communication_between_me_and_myagents/handoffs/`

For this task, the main agent acts as project director and quality gate owner.
Implementation should be delegated to focused subagents using document handoff.
Do not call any LLM, do not implement generation prompts, and do not modify the
source dataset.
