# Справочник пакетов: apt, dnf, rpm

Теги **`apt`**, **`dnf`**, **`rpm`**. Плейбуки осмотра: `aptq`, `rpmq`.  
`install` / `remove` / `apt update` — не в плейбуке.  
`apt-get -s` и `dnf --assumeno` показывают предполагаемую транзакцию, но не применяют её.

```bash
python3 src/seed_pkg.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$PKG=curl
!! pkvars[1]
!! aptq[1]
!! rpmq[1]
```

---

## apt / dpkg (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `apt-cache policy $PKG` | Кандидат / installed |
| 2 | `apt-cache show $PKG` | Описание |
| 3 | `apt-cache search $PKG` | Поиск |
| 4 | `apt list --installed \| grep $PKG` | Установлен? |
| 5 | `apt list --upgradable` | Обновления |
| 6 | `dpkg -l $PKG` | Статус dpkg |
| 7 | `dpkg -L $PKG` | Файлы |
| 8 | `dpkg -S $PKG` | Кто владеет |
| 9 | `apt update` | Обновить индексы |
| 10 | `apt install $PKG` | Поставить |
| 11 | `apt remove $PKG` | Убрать |
| 12 | `apt-get -s install $PKG` | Dry-run установки (план) |
| 13 | `apt-get -s remove $PKG` | Dry-run удаления (план) |
| 14 | `apt-cache depends $PKG` | Зависимости `$PKG` |
| 15 | `apt-cache rdepends $PKG` | Кто зависит от `$PKG` |

---

## dnf (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `dnf info $PKG` | Info |
| 2 | `dnf list installed $PKG` | Установлен? |
| 3 | `dnf search $PKG` | Поиск |
| 4 | `dnf check-update` | Обновления |
| 5 | `dnf repoquery -l $PKG` | Файлы |
| 6 | `yum info $PKG` | yum |
| 7 | `dnf install $PKG` | Поставить |
| 8 | `dnf remove $PKG` | Убрать |
| 9 | `dnf install --assumeno $PKG` | Dry-run установки (план) |
| 10 | `dnf remove --assumeno $PKG` | Dry-run удаления (план) |
| 11 | `dnf repoquery --requires $PKG` | Зависимости `$PKG` |
| 12 | `dnf repoquery --whatrequires $PKG` | Кто требует `$PKG` |

---

## rpm (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `rpm -q $PKG` | Установлен? |
| 2 | `rpm -qi $PKG` | Info |
| 3 | `rpm -ql $PKG` | Файлы |
| 4 | `rpm -qc $PKG` | Конфиги |
| 5 | `rpm -qf $PKG` | Путь → пакет |
| 6 | `rpm -Va $PKG` | Verify |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `aptq[1]` | policy → list --upgradable |
| `rpmq[1]` | `rpm -q` → `rpm -qi` |
