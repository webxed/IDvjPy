# Справочник основных консольных команд Linux

База тегов строится в порядке: **процессы → файлы → сеть → kubectl**. Ссылки вида `!proc[1]`, `!file[2]`, `!net[3]`, `!kube[1]` соответствуют одной и той же команде.

**В приложении:**
- `?` — список тегов
- `?proc` / `?file` / `?net` / `?kube` — команды тега с tid
- `!proc[1]` — подставить команду в строку ввода
- `!! proc[1]; file[2]` — собрать цепочку

**Заполнить БД:** `python3 seed_linux_commands.py --seed`

---

## proc — процессы

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ps aux` | Список процессов |
| 2 | `top` | Интерактивный монитор процессов |
| 3 | `htop` | Удобный монитор (если установлен) |
| 4 | `kill` | Завершить процесс по PID |
| 5 | `killall` | Завершить по имени |
| 6 | `pkill` | Завершить по шаблону имени |
| 7 | `nohup` | Запуск, устойчивый к разрыву сессии |
| 8 | `jobs` | Список фоновых заданий оболочки |
| 9 | `fg` | Вернуть задание на передний план |
| 10 | `bg` | Продолжить в фоне |

В приложении: `!proc[1]` … `!proc[10]`.

---

## file — файлы и каталоги

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ls -la` | Список файлов с деталями |
| 2 | `cp -r src dest` | Копирование рекурсивно |
| 3 | `mv src dest` | Перемещение или переименование |
| 4 | `rm -i` | Удаление с подтверждением |
| 5 | `mkdir -p` | Создать каталог и родителей |
| 6 | `rmdir` | Удалить пустой каталог |
| 7 | `touch` | Создать пустой файл / обновить время |
| 8 | `cat` | Вывести содержимое файла |
| 9 | `less` | Постраничный просмотр |
| 10 | `head` | Первые строки вывода |
| 11 | `tail -f` | Последние строки, следить за файлом |

В приложении: `!file[1]` … `!file[11]`.

---

## net — сеть

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ss -tulnp` | Сокеты (порты) TCP/UDP |
| 2 | `ping -c 3` | Проверка доступности хоста |
| 3 | `curl -sI` | HTTP‑запрос, только заголовки |
| 4 | `wget -qO-` | Скачать в stdout |
| 5 | `ssh` | Подключение по SSH |
| 6 | `rsync -avz` | Синхронизация по сети |
| 7 | `scp` | Копирование через SSH |
| 8 | `ip addr` | Адреса интерфейсов |
| 9 | `ip route` | Таблица маршрутизации |

В приложении: `!net[1]` … `!net[9]`.

---

## kube — Kubernetes (kubectl + tsh)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `tsh kube login CLUSTER` | Авторизация Teleport в Kubernetes-кластере |
| 2 | `kubectl config get-contexts` | Список kube context |
| 3 | `kubectl config current-context` | Текущий context |
| 4 | `kubectl cluster-info` | Информация о кластере |
| 5 | `kubectl get ns` | Список namespace |
| 6 | `kubectl get all -n $NS` | Все ресурсы в namespace `$NS` |
| 7 | `kubectl get pods -n $NS` | Поды в namespace `$NS` |
| 8 | `kubectl describe pod POD -n $NS` | Детали по pod |
| 9 | `kubectl logs POD -n $NS` | Логи pod |
| 10 | `kubectl logs -f POD -n $NS` | Логи pod (follow) |
| 11 | `kubectl exec -it POD -n $NS -- sh` | Exec внутрь pod |
| 12 | `kubectl get deploy -n $NS` | Deployments в namespace `$NS` |
| 13 | `kubectl describe deploy DEPLOY -n $NS` | Детали по deployment |
| 14 | `kubectl rollout status deploy/DEPLOY -n $NS` | Статус rollout |
| 15 | `kubectl rollout restart deploy/DEPLOY -n $NS` | Рестарт rollout |
| 16 | `kubectl get svc -n $NS` | Services в namespace `$NS` |
| 17 | `kubectl port-forward svc/SVC 8080:80 -n $NS` | Port-forward на service |
| 18 | `kubectl apply -f FILE.yaml -n $NS` | Применить манифест в namespace `$NS` |
| 19 | `kubectl delete -f FILE.yaml -n $NS` | Удалить манифест в namespace `$NS` |

В приложении: `!kube[1]` … `!kube[19]`.
