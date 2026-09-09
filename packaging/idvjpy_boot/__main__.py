"""Запуск установленного пакета через ``python -m idvjpy_boot``.

Консольная команда ``idvjpy`` указывает на ``idvjpy_boot:main``; этот модуль
даёт тот же запуск для ``python -m idvjpy_boot`` (полезно при отладке
установленного пакета без console script).
"""
from idvjpy_boot import main

if __name__ == "__main__":
    main()
