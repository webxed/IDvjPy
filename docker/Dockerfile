# syntax=docker/dockerfile:1
# IDvjPy_term — демостенд: маленький образ с TUI и готовой библиотекой тегов.
# Как запускать и что попробовать — docker/README.md.

FROM python:3.12-alpine

# bash            — приложение гоняет команды и TTY-сессии через /bin/bash (src/app.py);
# ncurses-terminfo-base — terminfo: без него Textual не знает про TERM=xterm-256color;
# nano            — редактор по умолчанию из settings.example.yml (`:editor`);
# git/curl/jq/procps — чтобы команды из seed-библиотеки реально выполнялись.
RUN apk add --no-cache \
        bash \
        curl \
        git \
        jq \
        nano \
        ncurses-terminfo-base \
        procps

# UTF-8 и предсказуемый вывод внутри контейнера.
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    TERM=xterm-256color \
    IDVJPY_APP_DIR=/app \
    IDVJPY_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения плюс .md-справочники (`:md`, ссылки из `?`).
COPY app.py backup_db.py ./
COPY src/ ./src/
COPY docs/ ./docs/
COPY K8S_CHAINS.md DEMO.md DATABASE.md ./
COPY docker/entrypoint.sh /usr/local/bin/idvjpy-demo
COPY docker/tui-smoke.py /usr/local/bin/tui-smoke.py
RUN chmod +x /usr/local/bin/idvjpy-demo /usr/local/bin/tui-smoke.py

# Данные (settings.yml, БД тегов, history) — в томе: переживают пересборку,
# сбрасываются удалением тома (docker volume rm idvjpy-demo-data).
WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["/usr/local/bin/idvjpy-demo"]
