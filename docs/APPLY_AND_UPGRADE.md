# Apply, configure, test, upgrade, and rollback

## Scope

This procedure installs only the DeepTutor-side integration. Obtain and deploy any RemNote-side plugin/service separately. Do not copy production tokens or databases into this repository.

## 1. Apply at the verified baseline

```bash
git clone https://github.com/HKUDS/DeepTutor.git
cd DeepTutor
git checkout 897fce52f24bf22e6e50d8a3e4df532632a26322
git apply --check /path/to/deeptutor-remnote-patch/patches/deeptutor-remnote.patch
git apply /path/to/deeptutor-remnote-patch/patches/deeptutor-remnote.patch
python -m compileall -q deeptutor/capabilities/remnote deeptutor/api/routers/knowledge.py
git diff --check
```

The patch has 26 `diff --git` paths. Confirm that count before applying:

```bash
grep -c '^diff --git ' /path/to/deeptutor-remnote-patch/patches/deeptutor-remnote.patch
```

## 2. Configure the server-owned connection

Copy `examples/remnote-connections.example.json` outside the repository and replace the placeholders. Keep the file mode `0600` and owned by the DeepTutor service account.

```bash
export DEEPTUTOR_REMNOTE_CONNECTIONS=/etc/deeptutor/remnote-connections.json
```

For private Docker-network HTTP, both controls are required:

```bash
export DEEPTUTOR_REMNOTE_ALLOW_PRIVATE_HTTP=1
export DEEPTUTOR_REMNOTE_PRIVATE_HTTP_HOSTS=remnote-sync
```

The host allowlist is exact. Do not use wildcards, CIDRs, raw public IPs, or browser-provided URLs.

Optional administrator pairing/proxy routes also require the server-side environment described in the patch and a private admin token. Keep `/admin/*` on the RemNote service inaccessible from the public reverse proxy.

## 3. Run focused tests

Install DeepTutor's server dependencies and pytest in an isolated environment. Create a credential-free minimal runtime config:

```bash
mkdir -p data/user/settings
cat > data/user/settings/main.yaml <<'YAML'
system:
  language: en
logging:
  level: WARNING
YAML
```

Then run:

```bash
DEEPTUTOR_HOME="$PWD" PYTHONPATH="$PWD" \
python -m pytest -p no:cacheprovider \
  /path/to/deeptutor-remnote-patch/tests/test_integration.py \
  tests/api/test_knowledge_router.py -q

cd web
npm ci --legacy-peer-deps
npm run typecheck
npm run test:node
```

The repository CI applies the patch to the exact baseline and runs these gates.

## 4. Runtime acceptance

Before replacing an existing deployment:

1. Preserve the current container/image and back up DeepTutor data/configuration.
2. Build a candidate image from the patched checkout.
3. Verify service health and authentication.
4. Select a configured RemNote KB and exercise `status`, `search`, `read`, and `navigate`.
5. Confirm source links use `https://www.remnote.com/w/{KB ID}/{Rem ID}`.
6. Confirm RemNote embedding settings appear only under the connected KB settings page.
7. Confirm browser responses/metadata never expose read/admin/API keys.
8. Verify unrelated local DeepTutor repairs separately before cutover.

## 5. Port to a newer DeepTutor revision

Never reset or overwrite an active locally patched DeepTutor tree.

1. Record the target upstream commit and existing dirty/untracked paths.
2. Create a disposable worktree at the new revision.
3. Run `git apply --check` there.
4. Review every touched symbol for API and behavioral compatibility; textual applicability alone is insufficient.
5. Port only RemNote behavior. Keep unrelated Selection Tutor/session fixes in a separate patch stream.
6. Run focused backend tests, frontend typecheck/node tests, image-backed acceptance, and a real capability turn.
7. Regenerate this patch against the new exact baseline only after deployment succeeds.

## 6. Rollback

Rollback means restoring the prior DeepTutor image/container and source revision. Do not delete or rotate RemNote credentials merely because the DeepTutor patch is rolled back. Verify the previous deployment is healthy before removing the failed candidate.
