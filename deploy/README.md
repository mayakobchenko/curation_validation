# Deploying the Curation Validator on the EBRAINS Kubernetes cluster (GitOps)

```
git push ──► GitHub Actions ──► builds image, pushes to Harbor (docker-registry.ebrains.eu)
                         └──► commits the new image tag to deploy/helm/curation-validator/values-*.yaml
Argo CD (gitops.apps.dev-jsccloud.ebrains.eu) ──► sees the commit ──► renders the chart ──► rolls out
Vault ──► Kubernetes Secret `curation-validator-secrets` ──► read by the pod (never stored in Git)
```

## What is in the repo
| Path | Purpose |
|---|---|
| `deploy/helm/curation-validator/` | our own Helm chart (Deployment, Service, Ingress, PVC, optional ExternalSecret) |
| `.../values.yaml`, `values-dev.yaml`, `values-prod.yaml` | settings; **no secrets**, CI edits only `image.tag` |
| `deploy/argocd/curation-validator-{dev,prod}.yaml` | the Argo CD `Application` objects (dev follows branch `main`, prod follows `production`) |
| `.github/workflows/ci-cd.yml` | build + push image, bump the tag in Git (no kubeconfig needed any more) |

## What has to be whitelisted / provided by IT
1. **Git repository** for Argo CD (the "chart URL"): `https://github.com/mayakobchenko/curation_validation.git`, path `deploy/helm/curation-validator`. The chart is our own; it uses **no third-party chart repositories**.
2. **Container registry**: `docker-registry.ebrains.eu` (images `ebrains-data-curation/curation-validator[-dev/...]`).
3. **Namespaces** (`curation-validator-dev`, `curation-validator`) and the Argo CD project name.
4. **Vault**: a path holding two keys, `CURATION_VALIDATOR_OIDC_CLIENT_SECRET` and `SESSION_SECRET`, and the mechanism that turns it into the Kubernetes Secret `curation-validator-secrets` (see `values.yaml`, section `secrets`).
5. **Host name** (e.g. `curation-validator-dev.apps.dev-jsccloud.ebrains.eu`) and a Keycloak (IAM) client whose redirect URI is `https://<host>/auth/callback`.

## Secrets: generate once, store in Vault
- `SESSION_SECRET`: a long random string, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `CURATION_VALIDATOR_OIDC_CLIENT_SECRET`: from the IAM client.
Never commit either to this repository (it is public).

## Check a chart locally
```
helm lint deploy/helm/curation-validator -f deploy/helm/curation-validator/values-dev.yaml
helm template cv deploy/helm/curation-validator -f deploy/helm/curation-validator/values-dev.yaml
```
