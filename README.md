# EBRAINS Curation Validator

A web app that replaces the manual `curation-validation_<UUID>.md` checklist:
a secondary curator reviews a primary curator's dataset-curation work in the
EBRAINS Knowledge Graph (KG) through a form instead of a Word/markdown
document, with as much of the checking automated as is safely possible.

Sister project to [`updated-metadata-wizard`](https://github.com/mayakobchenko/updated-metadata-wizard) — same KG, same IAM realm, same
Kubernetes cluster, same CI/CD shape, so this README only calls out what
differs.

## What's automated vs. manual

| Checklist table | Automated? |
|---|---|
| 1. Dataset info | form fields, carried through to the export |
| 2. Secondary curator info | form field |
| 3. Data Descriptor checks | file present, no template text (automatic); content match and proofreading from the **AI review** (suggestion) |
| 4. Structure & file storage | **manual** |
| 5a. Dataset / DSV fields | **automated**: required-field presence pulled live from the KG, DOI resolution, and a DS-vs-DSV duplication check (per the form's inheritance rule — identical values on both DS and DSV are flagged since they should live on the DS card only) |
| 5b/5c. Subject / tissue sample fields | **automated**: required-field presence pulled live from the KG |
| 5d. Project | manual (presence of a linked Project isn't yet pulled) |
| 6. File repository | bucket exists, data descriptor PDF and licence file present (automatic); the rest manual |

Automated results show as a suggestion (✅/❌/–) next to each item; the
secondary curator's own Yes/No/N/A answer is always what gets saved and
exported — nothing here auto-signs-off a dataset.

The "open 5 tabs" step (data descriptor, metadata overview, dataset
preview, DSV in KG Editor, collab bucket) is replaced by **Start new
validation**: paste the DatasetVersion UUID and the app pulls the DS, DSV,
subjects/groups and tissue samples/collections from the KG in one call.

## What is fetched for you

A validation needs only the **dataset version UUID** and the **GitLab issue URL**. With the curator's own EBRAINS token
the app then fetches:

- **Knowledge Graph** (`kg_client.py`): the dataset version, its parent dataset, and everything in the collab space
  `collab-d-<uuid>`: subjects, subject groups, tissue samples, tissue sample collections with all their states, and what
  they point to (persons, ORCIDs, species, strains, licence, techniques ...). The title, version and persons fill in
  by themselves.
- **Collab drive** (`drive_client.py`, scope `collab.drive`): `data-descriptor_<id>.doc(x)` (read to text in
  `descriptor.py`; an old `.doc` needs LibreOffice, which the image has) and the wizard's `metadata_wizard_draft.json`.
- **Data Proxy bucket** `d-<uuid>` (`bucket_client.py`): file names, sizes and the `sub-xxx` identifiers in them.
  Names only, no file contents.

`compare.py` compares the metadata draft with the KG (title, description, persons, ORCIDs, subjects and their states,
groups, tissue samples, collections) and the bucket's subject identifiers with the KG subjects. `checks.py` turns all of it
into the suggestions next to the checklist items (with the fetched value or the reason in the note).

A source that cannot be fetched (no drive access, no bucket) is reported on the *Sources* tab and does not stop the
validation.

### AI review

The *AI review* tab sends the text of the data descriptor, the KG metadata, the differences found by the comparison and the
bucket's file names to a language model (any service that speaks the OpenAI chat-completions protocol, such as GPT UiO)
and shows its findings. It only suggests: the curator's own answers are never changed. Configure it with `LLM_BASE_URL`,
`LLM_API_KEY` (a secret, kept on the server), `LLM_MODEL`, `LLM_LABEL`, `LLM_MAX_TOKENS_PARAM` (see `.env.example`; in the
Helm chart `llm.*` and the Vault key `LLM_API_KEY`). The descriptor and the metadata can contain personal data: use a
service that the data may be sent to.

Tests: `cd backend && pip install -r requirements.txt -r requirements-dev.txt && python -m pytest`.

## Stack

- **Backend**: Python / FastAPI, `httpx` for the KG + IAM calls, `python-docx` for the Word export (PDF via LibreOffice headless conversion in the container)
- **Frontend**: React 19 / Vite / Ant Design v5 (deliberately the same choices as the wizard)
- **Auth**: EBRAINS IAM/Keycloak, realm `hbp` — but unlike the wizard's service-account (`client_credentials`) flow, this app needs to know *which curator* is reviewing, so it uses the browser authorization-code flow (`/auth/login` → IAM → `/auth/callback`), with the curator's own KG access token kept server-side in a signed session cookie
- **Storage**: one JSON file per validation run under `DATA_DIR`, named `curation-validation_<uuid>.json` — matches the existing manual-form naming convention; swap for a real DB later if volume ever justifies it

## Local development

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DEV_MODE=true uvicorn app.main:app --reload --port 4100

# frontend (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api and /auth to :4100
```

Open http://localhost:5173 and click **Log in**.

`DEV_MODE=true` is what makes this work before an EBRAINS IAM OIDC client
exists for this app: it skips the real IAM redirect and logs in a fake
"Dev Curator" straight away, so you can click through the dashboard, the
"start new validation" form, the checklist tabs and the export buttons.
It's for seeing the UI only — **Pull from KG & start validation** will
still fail (no real KG access token in dev mode), since that needs an
actual EBRAINS login. Once Eivind sets up a real OIDC client, drop
`DEV_MODE` and fill in `.env` (copy `.env.example`) with
`CURATION_VALIDATOR_OIDC_CLIENT_ID`/`_SECRET` instead, and the full flow
— including real KG pulls — will work locally too, no Kubernetes needed
for that either.

Never set `DEV_MODE=true` in a deployed environment — it bypasses login
entirely.

## One-time setup still needed (not something I can do from here)

1. **GitHub repo**:
   ```bash
   git init && git add -A && git commit -m "Scaffold curation validator"
   git remote add origin https://github.com/mayakobchenko/curation-validator.git
   git push -u origin main
   ```
2. **EBRAINS IAM/Keycloak OIDC client** — a new client (distinct from the
   wizard's `ebrains-wizard-dev` service-account client) is needed in the
   `hbp` realm, configured for the **authorization-code flow** (not
   client-credentials) with redirect URIs pointing at this app's `/auth/callback`
   on each environment. Eivind owns client creation on this realm, same as
   for the wizard.
3. **Kubernetes** — same cluster (`c-4qp8z`) as the wizard, but its own
   namespace/Deployment/Service/Ingress, created once via the Rancher UI
   (the wizard's CI/CD only ever patches an existing Deployment's image —
   it never creates the Deployment itself — so this repo mirrors that and
   has no k8s manifests in it; the Deployment/Service/Ingress for
   `curation-validator-dev` / `curation-validator` namespaces need to be
   created in Rancher first, same steps Nikos used for the wizard).
4. **GitHub Actions secrets** — `HARBOR_USERNAME`, `HARBOR_PASSWORD`,
   `KUBE_CONFIG_JSC`, `KUBE_CONFIG_JSC_PROD` on the new repo (can reuse the
   wizard's values if they're org-level secrets; otherwise copy them over
   as repo secrets).
5. Decide the Harbor project path (`.github/workflows/ci-cd.yml` currently
   assumes `ebrains-data-curation/curation-validator{-dev}`, following the
   wizard's existing project) and confirm with Nikos if a new Harbor
   project/robot account is needed.

## Repo layout

```
backend/app/
  main.py          FastAPI app, mounts auth + validation + export routers, serves built SPA
  config.py        env-driven settings
  auth.py          IAM/Keycloak login (auth-code flow) + session cookie
  kg_client.py      KG v3 REST pulls (instance, neighbors, per-space listing)
  models.py        Pydantic models mirroring the checklist tables 1-6
  checks.py        mechanical checks: required-field presence, DS/DSV duplication, DOI/URL resolution
  export.py        docx/pdf rendering of a completed run
  storage.py       JSON-file persistence, one file per run
  routes/
    validation.py   start/get/update/refresh/submit a run
    export_routes.py  docx/pdf download endpoints
frontend/src/
  pages/           Dashboard, NewValidation, ValidationForm
  components/      TopBar, CheckTable
  api.js           fetch wrapper
Dockerfile          single-container build (mirrors the wizard's pattern): builds the
                    React app, then a Python/FastAPI image that serves both the API
                    and the built SPA on one port
.github/workflows/ci-cd.yml   build → push to Harbor → patch the Deployment's image on the existing cluster
```
## to run locally
```
# terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DEV_MODE=true uvicorn app.main:app --reload --port 4100

on windows cmd:
cd backend
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set DEV_MODE=true
uvicorn app.main:app --reload --port 4100

deactivate

# terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, click Log in — you'll land straight in the dashboard. You can click through the "start new validation" form and the checklist tabs, but actually pulling a dataset from the KG will fail in dev mode since that genuinely needs your EBRAINS login — that part only becomes testable once the real OIDC client exists.