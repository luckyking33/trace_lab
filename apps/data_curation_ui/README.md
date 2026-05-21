# Mechanism DG Local Data Curation UI

Local full-stack tool for manually curating mechanism-ready JSONL items from raw datasets.

This app does not automatically select items, generate distractors, read original options, or append unreviewed data. It helps a researcher inspect raw records, hand-fill a mechanism-ready item, validate mechanism-only constraints, and append confirmed JSONL rows. Optional DeepSeek helpers are available for translation and draft annotation only when explicitly clicked.

## Layout

```text
apps/data_curation_ui/
  backend/   FastAPI app, Arrow loader, workspace/draft store, validation, JSONL append
  frontend/  React + Vite + TypeScript three-column curation UI
```

Runtime metadata is written under the repository root:

```text
.dg_curation/workspaces.json
.dg_curation/drafts/{workspace_id}/{dataset_id}_{index}.json
.dg_curation/append_log.jsonl
```

## Backend

From the repository root:

```bash
cd apps/data_curation_ui/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8766
```

On Windows PowerShell:

```powershell
cd apps\data_curation_ui\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8766
```

Health check:

```text
http://localhost:8766/api/health
```

## Frontend

From the repository root:

```bash
cd apps/data_curation_ui/frontend
npm install
npm run dev
```

The frontend defaults to:

```text
http://127.0.0.1:8766
```

To use a different backend URL, create `apps/data_curation_ui/frontend/.env`:

```text
VITE_API_BASE=http://127.0.0.1:8766
```

Then open:

```text
http://localhost:5173
```

## Basic Use

1. Start the backend and frontend.
2. Create a workspace from the top bar.
3. Load the Arrow dataset path:

```text
data/competition_math/train/data-00000-of-00001.arrow
```

4. Browse records with Previous, Next, or Jump to index.
5. Set output directory and filename, for example:

```text
data/derived_no_options
mechanism_toy_50.jsonl
```

6. Fill the mechanism-ready form manually.
7. Use Save Draft / Load Draft / Clear Draft for the current source record.
8. Watch the validation panel. Append is blocked until required fields, leakage flags, quality-control flags, trace length, operator count, counterfactual count, output path, and duplicate checks pass.
9. Click `Confirm Add to JSONL`.

## JSONL Viewer

Use the top page switcher to open `JSONL 查看` / `JSONL viewer`.

1. Enter a repository-relative `.jsonl` path, for example:

```text
data/mechanism_toy_50.template.jsonl
```

The JSONL viewer currently defaults to:

```text
data/mechanism_invariant_operator_45.jsonl
```

2. Click `加载 JSONL` / `Load JSONL`.
3. Browse rows from the left record list or with Previous / Next / Jump.
4. Fields are rendered with the same cards/tree display used by the data curation page, including Chinese field explanations, LaTeX rendering, leakage warnings, and AI Chinese translation for question-like fields.

Successful append reports the appended `item_id`, output path, and current item count.

## Safety Rules

- Output filename must end in `.jsonl`.
- Paths must resolve inside the repository root.
- Path traversal with `..` is rejected.
- Reading or writing inside `data/source_quarantine/` is rejected.
- Existing output files are appended to, never overwritten.
- Duplicate `item_id` values in the selected output JSONL are rejected.
- Forbidden mechanism-only leakage keys are rejected recursively.
- Raw fields such as `choices`, `options`, `distractors`, `student_choice`, `human_response_dist`, `seed_candidates`, and `item_stats` are marked red in the viewer and cannot be copied into the output item.

## Tests

From the repository root:

```bash
python -m pytest apps/data_curation_ui/backend/tests -q
```

The tests cover missing Arrow paths, Arrow metadata and record loading, valid item validation, required field rejection, forbidden key rejection, duplicate `item_id` rejection, `source_quarantine` path rejection, valid append, and append logging.

## Known Limits

- The output schema is the richer prompt-defined mechanism-ready format, not the repository's older `schemas/item_schema.json`.
- JSON preview is read-only. Form mode is the intended editing surface.
- The output viewer shows status and last item only; it does not edit or delete previously appended rows.
- The UI does not render LaTeX with MathJax yet; it preserves the original text so LaTeX remains readable.
- Search, keyboard shortcuts, validation report export, and advanced output item browsing are not implemented in this MVP.
