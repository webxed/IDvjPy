# Справочник HashiCorp Vault для IDvjPy

Тег **`vault`**. Плейбуки: `vstat`, `vkv`, `vapprole` (осмотр и вход).  
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

## AppRole: вход (тег `vapprole`)

Сценарий: токен → имя роли → `role_id` → `secret_id` → `login` → временный токен.
Значения из таблиц `vault` переносятся в переменные прямо из вывода блока — запись
`$VAR=@key` / `$$VAR=@key` берёт остаток строки, первый токен которой равен
`key` (учитывается только сфокусированный или последний **завершённый** блок).
`@last` — последняя непустая строка (удобно после `| jq -r .field`).

Шаги размечены директивами прогона (`run:`): где нужно решение человека —
`run:manual`, остальное идёт само. Поэтому цепочка запускается одной командой
`:run vapprole` (см. `:? run`): прогон встанет на токене, на имени роли и на
выпуске `secret_id`, а `role_id`/`secret_id`/`token` заберёт из вывода блоков.
Шаги 1 и 2 — строки-префиксы (`$$VAULT_TOKEN=`, `$ROLE=`): значение
**дописывается после `=`**, поэтому Enter с нетронутой строкой не отправит
вымышленное имя роли (раньше там стояло `$ROLE=custom-role`, и Enter выполнял его).

| tid | Шаг | Режим | Что делает |
|-----|-----|-------|------------|
| 1 | `$$VAULT_TOKEN=` | `run:manual` | токен из vault.website: вставьте значение после `=` и Enter |
| 2 | `$ROLE=` | `run:manual` | имя AppRole: допишите после `=` (напр. `custom-role`) |
| 3 | `vault read auth/approle/role/$ROLE/role-id` | `run:auto` | `role_id` |
| 4 | `$$ROLE_ID=@role_id` | `run:auto` | секрет из шага 3 |
| 5 | `vault write -force auth/approle/role/$ROLE/secret-id` | `run:manual` | новый `secret_id` (выпуск — по подтверждению) |
| 6 | `$$SECRET_ID=@secret_id` | `run:auto` | секрет из шага 5 |
| 7 | `vault write auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID"` | `run:auto` | вход, `token` |
| 8 | `$$VAULT_TOKEN=@token` | `run:auto` | обновить токен |
| 9 | `vault read $SECRET` | `run:auto` | проверка доступа новым токеном |

```text
# вся цепочка (полуавтомат): останавливается там, где нужен человек
:run vapprole

# то же, но с остановкой на каждом шаге (править строку и Enter),
# или без выполнения — только план:
:run vapprole --step
:run vapprole --dry

# прервать между шагами: Esc или
:run stop
```

Вручную те же шаги остаются в библиотеке: `!vapprole[N]` вставляет строку во ввод,
запуск — отдельным Enter (`$$VAR=@key` — префикс переменной, его нельзя приклеить
к команде через `;`). В `:run` шаг с `run:manual` вставляет строку сам и ждёт,
а пустой Enter пропускает шаг (например, токен уже есть); шаги 1–2 надо
дополнить значением после `=`.

Готовая строка логина с подставленными значениями: после шага 7 (блок login)
`:cmd` кладёт в буфер обмена раскрытую команду
`vault write auth/approle/login role_id="2474…" secret_id="3ab7…"`;
в журнал попадает маскированная версия (`****`), `:cmd show` печатает полную строку.

Секреты (`$$…`) не показываются на экране и живут только до выхода из
приложения (`secrets_<instance>.json` удаляется при выходе).

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
