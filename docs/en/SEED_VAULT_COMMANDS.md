# HashiCorp Vault handbook for IDvjPy

Tag **`vault`**. Playbooks: `vstat`, `vkv`, `vapprole` (inspection and login).  
`kv get` prints secrets **to the journal** — not part of the auto-chain; for path inspection use `kv metadata get`.

`vvars` does not print `VAULT_TOKEN`, only `token=set` / `token=unset`.

```bash
python3 src/seed_vault.py --seed
# or together with the rest of ops:
python3 src/seed_ops.py --seed
```

```text
$VAULT_ADDR=https://vault.example.com:8200
$VAULT_NAMESPACE=
$MOUNT=secret
$SECRET=secret/app
$ROLE=
$POLICY=default
$FIELD=
!! vvars[1]
```

The token lives in the environment (`export VAULT_TOKEN=…` or `vault login`), not in seed commands.

---

## vault — commands (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `vault status` | Sealed / HA / version |
| 2 | `vault status -format=json` | JSON → F5 |
| 3 | `vault read sys/health` | Health via CLI |
| 4 | `curl -sS $VAULT_ADDR/v1/sys/health` | Health HTTP, often without a token |
| 5 | `vault auth list` | Auth methods |
| 6 | `vault secrets list` | Secret engines |
| 7 | `vault policy list` | Policies |
| 8 | `vault policy read $POLICY` | Text of `$POLICY` |
| 9 | `vault audit list` | Audit devices |
| 10 | `vault token lookup` | TTL and policies of the current token |
| 11 | `vault token lookup -format=json` | Lookup JSON |
| 12 | `vault kv list $MOUNT` | Keys on `$MOUNT` |
| 13 | `vault kv list $SECRET` | Keys in `$SECRET` |
| 14 | `vault kv metadata get $SECRET` | Metadata, without values |
| 15 | `vault kv metadata get -format=json $SECRET` | Metadata JSON |
| 16 | `vault kv get $SECRET` | **Secret values to the journal** |
| 17 | `vault kv get -field=$FIELD $SECRET` | Single field |
| 18 | `vault operator raft list-peers` | Raft peers |
| 19 | `vault operator raft autopilot state` | Autopilot |
| 20 | `vault read auth/approle/role/$ROLE` | AppRole `$ROLE` |
| 21 | `vault login` | Login (`> vault login`) |
| 22 | `vault kv put $SECRET $FIELD=value` | Write (changes Vault) |

Not in the playbook: `operator seal`, `token revoke`, `kv delete` / `destroy`, `kv put`.

For KV v2 the CLI path is `secret/app`, not `secret/data/app`.

---

## AppRole: login (tag `vapprole`)

Scenario: token → role name → `role_id` → `secret_id` → `login` → temporary token.
Values from the `vault` tables are carried into variables straight from block output — the entry
`$VAR=@key` / `$$VAR=@key` takes the rest of the line whose first token equals
`key` (only the focused or the last **finished** block is considered).
`@last` — the last non-empty line (handy after `| jq -r .field`).

Steps are tagged with run directives (`run:`): where a human decision is needed —
`run:manual`, the rest runs on its own. That is why the chain is started with a single command
`:run vapprole` (see `:? run`): the run will stop at the token, at the role name and at
issuing `secret_id`, while `role_id`/`secret_id`/`token` are taken from block output.
Steps 1 and 2 — prefix lines (`$$VAULT_TOKEN=`, `$ROLE=`): the value is
**appended after the `=`**, so Enter with an untouched line will not send a
made-up role name (it used to be `$ROLE=custom-role`, and Enter would run it).

| tid | Step | Mode | What it does |
|-----|------|------|--------------|
| 1 | `$$VAULT_TOKEN=` | `run:manual` | token from vault.website: paste the value after `=` and press Enter |
| 2 | `$ROLE=` | `run:manual` | AppRole name: type it after `=` (e.g. `custom-role`) |
| 3 | `vault read auth/approle/role/$ROLE/role-id` | `run:auto` | `role_id` |
| 4 | `$$ROLE_ID=@role_id` | `run:auto` | secret from step 3 |
| 5 | `vault write -force auth/approle/role/$ROLE/secret-id` | `run:manual` | new `secret_id` (issuing — on confirmation) |
| 6 | `$$SECRET_ID=@secret_id` | `run:auto` | secret from step 5 |
| 7 | `vault write auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID"` | `run:auto` | login, `token` |
| 8 | `$$VAULT_TOKEN=@token` | `run:auto` | update the token |
| 9 | `vault read $SECRET` | `run:auto` | check access with the new token |

```text
# the whole chain (semi-automatic): stops where a human is needed
:run vapprole

# the same, but stopping at every step (edit the line and press Enter),
# or without executing — plan only:
:run vapprole --step
:run vapprole --dry

# interrupt between steps: Esc or
:run stop
```

Manually the same steps stay in the library: `!vapprole[N]` inserts the line into the input,
the run is a separate Enter (`$$VAR=@key` is a variable prefix, it cannot be glued
to a command with `;`). In `:run` a step with `run:manual` inserts the line itself and waits,
while an empty Enter skips the step (for example, the token already exists); steps 1–2 must be
completed with a value after `=`.

The ready login line with substituted values: after step 7 (the login block)
`:cmd` puts the expanded command into the clipboard
`vault write auth/approle/login role_id="2474…" secret_id="3ab7…"`;
the journal gets a masked version (`****`), `:cmd show` prints the full line.

Secrets (`$$…`) are not shown on screen and live only until the app exits
(`secrets_<instance>.json` is deleted on exit).

---

## Playbooks

| Tag | Chain |
|-----|-------|
| `vstat[1]` | status → health HTTP → auth list → secrets list |
| `vkv[1]` | `kv list $SECRET` → `kv metadata get` |

```text
!! vstat[1]
$SECRET=secret/app
!! vkv[1]
```
