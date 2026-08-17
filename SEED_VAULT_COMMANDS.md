# Справочник HashiCorp Vault для IDvjPy

Тег **`vault`**. Плейбуки: `vstat`, `vkv` (осмотр).  
`kv get` печатает секреты **в журнал** — в автоцепочку не входит; для осмотра пути — `kv metadata get`.

`vvars` не печатает `VAULT_TOKEN`, только `token=set` / `token=unset`.

```bash
python3 src/seed_vault.py --seed
# или вместе с остальными ops:
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

Токен — в окружении (`export VAULT_TOKEN=…` или `vault login`), не в сид-командах.

---

## vault — команды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `vault status` | Sealed / HA / версия |
| 2 | `vault status -format=json` | JSON → F5 |
| 3 | `vault read sys/health` | Health через CLI |
| 4 | `curl -sS $VAULT_ADDR/v1/sys/health` | Health HTTP, часто без токена |
| 5 | `vault auth list` | Методы auth |
| 6 | `vault secrets list` | Secret engines |
| 7 | `vault policy list` | Политики |
| 8 | `vault policy read $POLICY` | Текст `$POLICY` |
| 9 | `vault audit list` | Audit devices |
| 10 | `vault token lookup` | TTL и policies текущего токена |
| 11 | `vault token lookup -format=json` | Lookup JSON |
| 12 | `vault kv list $MOUNT` | Ключи на `$MOUNT` |
| 13 | `vault kv list $SECRET` | Ключи в `$SECRET` |
| 14 | `vault kv metadata get $SECRET` | Метаданные, без значений |
| 15 | `vault kv metadata get -format=json $SECRET` | Metadata JSON |
| 16 | `vault kv get $SECRET` | **Значения секрета в журнал** |
| 17 | `vault kv get -field=$FIELD $SECRET` | Одно поле |
| 18 | `vault operator raft list-peers` | Raft peers |
| 19 | `vault operator raft autopilot state` | Autopilot |
| 20 | `vault read auth/approle/role/$ROLE` | AppRole `$ROLE` |
| 21 | `vault login` | Login (`> vault login`) |
| 22 | `vault kv put $SECRET $FIELD=value` | Запись (меняет Vault) |

Не в плейбуке: `operator seal`, `token revoke`, `kv delete` / `destroy`, `kv put`.

Для KV v2 путь в CLI — `secret/app`, не `secret/data/app`.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `vstat[1]` | status → health HTTP → auth list → secrets list |
| `vkv[1]` | `kv list $SECRET` → `kv metadata get` |

```text
!! vstat[1]
$SECRET=secret/app
!! vkv[1]
```
