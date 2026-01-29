"""
command_parser.py - Модуль для парсинга команд с поддержкой ссылок.

Использует pyparsing для надежного разбора команд вида:
- !tag[tid] - ссылка на команду по тегу и ID
- !ID - ссылка на команду по глобальному ID
- !! tag[tid] operator tag[tid] - сборка команд с операторами

v1.1.9 - Альтернативная реализация парсера (экспериментальная).
Используйте command_parser_v2.py для продакшн-кода.
"""

from typing import List, Tuple, Optional, Dict, Any
import sys

try:
    from pyparsing import (
        Word, alphas, alphanums, nums, Literal, Combine,
        Optional as Opt, infixNotation, opAssoc, ParserElement,
        QuotedString, Forward, Regex, oneOf, Group
    )
    PYPARSING_AVAILABLE = True
except ImportError:
    PYPARSING_AVAILABLE = False
    print("Warning: pyparsing not available, using fallback parser", file=sys.stderr)


class CommandToken:
    """Токен команды - ссылка или оператор."""

    def __init__(self, token_type: str, value: str, tag: Optional[str] = None,
                 tid: Optional[int] = None, global_id: Optional[int] = None):
        self.type = token_type  # 'tag_ref', 'global_ref', 'operator', 'double_bang'
        self.value = value
        self.tag = tag
        self.tid = tid
        self.global_id = global_id

    def __repr__(self):
        if self.type == 'tag_ref':
            return f"Token(tag_ref, {self.tag}[{self.tid}])"
        elif self.type == 'global_ref':
            return f"Token(global_ref, !{self.global_id})"
        elif self.type == 'operator':
            return f"Token(op, '{self.value}')"
        elif self.type == 'double_bang':
            return f"Token(!!)"
        return f"Token({self.type}, {self.value})"


class CommandParser:
    """
    Парсер команд с поддержкой ссылок на другие команды.

    Использует pyparsing для надежного разбора составных команд.
    """

    def __init__(self):
        self._setup_parser()

    def _setup_parser(self):
        """Настраивает грамматику pyparsing."""
        if not PYPARSING_AVAILABLE:
            return

        # Ускоряем парсинг
        ParserElement.enablePackrat()

        # Ссылка на команду по тегу: !tag[tid]
        tag_ref = Regex(r'![a-zA-Z_0-9]+\[\d+\]')
        tag_ref.setParseAction(self._parse_tag_ref)

        # Ссылка на команду по глобальному ID: !ID
        global_ref = Regex(r'!\d+')
        global_ref.setParseAction(self._parse_global_ref)

        # Операторы
        operator = Regex(r'&&?|\|\|?|;|&')

        # Двойной банг: !!
        double_bang = Literal('!!')

        # Обычный текст (все, что не специальные токены)
        # Захватываем текст между операторами и ссылками
        text_token = Regex(r'[^\s!&|;]+(?:\s+[^\s!&|;]+)*')

        # Грамматика для последовательного разбора
        # Простая цепочка: токен (оператор токен)*
        self.grammar = Forward()

        # Элементарный токен (может быть ссылкой или текстом)
        element = tag_ref | global_ref | text_token

        # Полная грамматика: элемент followed by (operator element)*
        self.grammar << (element +
                         Opt((operator + element) * 10))  # До 10 пар оператор-токен

    def _parse_tag_ref(self, tokens):
        """Парсит тег-ссылку !tag[tid]."""
        text = tokens[0]
        # text = "!tag[tid]"
        tag_end = text.find('[')
        tid_start = tag_end + 1
        tid_end = text.find(']', tid_start)

        tag = text[1:tag_end]
        tid = int(text[tid_start:tid_end])

        return CommandToken('tag_ref', text, tag=tag, tid=tid)

    def _parse_global_ref(self, tokens):
        """Парсит глобальную ссылку !ID."""
        text = tokens[0]
        # text = "!123"
        global_id = int(text[1:])
        return CommandToken('global_ref', text, global_id=global_id)

    def parse(self, command: str) -> List[CommandToken]:
        """
        Парсит команду и возвращает список токенов.

        Args:
            command: Строка команды для парсинга

        Returns:
            Список токенов (CommandToken)
        """
        if not PYPARSING_AVAILABLE:
            return self._fallback_parse(command)

        try:
            command = command.strip()
            tokens = []
            has_double_bang = command.startswith('!!')

            if has_double_bang:
                tokens.append(CommandToken('double_bang', '!!'))
                command = command[2:].strip()

            # Парсим остаток
            result = self.grammar.parseString(command)

            # Преобразуем результат в плоский список токенов
            def flatten(item):
                """Рекурсивно разворачивает ParseResults."""
                if isinstance(item, (list, tuple)):
                    for sub in item:
                        yield from flatten(sub)
                else:
                    yield item

            flat_result = list(flatten(result))

            # Обрабатываем каждый элемент
            for item in flat_result:
                if isinstance(item, CommandToken):
                    tokens.append(item)
                elif isinstance(item, str):
                    # Проверяем, не является ли строка оператором
                    if item.strip() in ('&', '&&', '|', '||', ';'):
                        tokens.append(CommandToken('operator', item.strip()))
                    elif item.strip():
                        # Обычный текст
                        tokens.append(CommandToken('text', item.strip()))

            return tokens

        except Exception as e:
            # При ошибке парсинга используем fallback
            print(f"Parse error: {e}, using fallback parser", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return self._fallback_parse(command)

    def _fallback_parse(self, command: str) -> List[CommandToken]:
        """
        Fallback-парсер на основе регулярных выражений.

        Используется когда pyparsing недоступен или при ошибках.
        """
        import re

        tokens = []
        command = command.strip()

        # Проверяем !!
        if command.startswith('!!'):
            tokens.append(CommandToken('double_bang', '!!'))
            command = command[2:].strip()

        # Парсим остаток
        # Ищем токены: tag[tid], ID, или текст
        pattern = r'([a-zA-Z_0-9]+\[\d+\]|\d+|"[^"]*"|\'[^\']*\'|[^!&|;\s]+)(\s*[&|;]\s*)?'

        pos = 0
        while pos < len(command):
            match = re.match(pattern, command[pos:])
            if not match:
                break

            token_text = match.group(1)
            separator = match.group(2) or ''

            # Определяем тип токена
            if '[' in token_text and token_text.endswith(']'):
                # tag[tid]
                tag_match = re.match(r'^([a-zA-Z_0-9]+)\[(\d+)\]$', token_text)
                if tag_match:
                    tag = tag_match.group(1)
                    tid = int(tag_match.group(2))
                    tokens.append(CommandToken('tag_ref', f"!{token_text}",
                                             tag=tag, tid=tid))
            elif token_text.isdigit() and command[pos-1:pos] == '!':
                # !ID (проверяем, что перед числом был !)
                tokens.append(CommandToken('global_ref', f"!{token_text}",
                                         global_id=int(token_text)))
            elif separator.strip() in ('&', '&&', '|', '||', ';'):
                # Оператор
                tokens.append(CommandToken('operator', separator.strip()))
            elif token_text.strip():
                # Обычный текст
                tokens.append(CommandToken('text', token_text))

            pos += len(token_text) + len(separator)

        return tokens

    def assemble_command(self, tokens: List[CommandToken],
                        get_command_fn) -> Optional[str]:
        """
        Собирает команду из токенов, раскрывая ссылки.

        Args:
            tokens: Список токенов от parse()
            get_command_fn: Функция для получения команды по ссылке
                           Принимает (tag, tid) или (global_id,)
                           Возвращает текст команды или None

        Returns:
            Собранная команда или None при ошибке
        """
        if not tokens:
            return None

        result_parts = []
        last_was_operator = True  # Чтобы не добавлять пробел в начале

        for token in tokens:
            if token.type == 'tag_ref':
                # Получаем команду по тегу и ID
                cmd_text = get_command_fn(tag=token.tag, tid=token.tid)
                if cmd_text is None:
                    return None
                result_parts.append(cmd_text)
                last_was_operator = False

            elif token.type == 'global_ref':
                # Получаем команду по глобальному ID
                cmd_text = get_command_fn(global_id=token.global_id)
                if cmd_text is None:
                    return None
                result_parts.append(cmd_text)
                last_was_operator = False

            elif token.type == 'operator':
                # Добавляем оператор
                result_parts.append(token.value)
                last_was_operator = True

            elif token.type == 'text':
                # Обычный текст
                result_parts.append(token.value)
                last_was_operator = False

        # Собираем результат с правильными разделителями
        result = []
        for i, part in enumerate(result_parts):
            if i > 0 and result_parts[i-1] not in ('&', '&&', '|', '||', ';'):
                # Добавляем пробел если предыдущий не оператор
                result.append(' ')
            result.append(part)

        return ''.join(result)


# Тестирование модуля
if __name__ == '__main__':
    def test_get_command(tag=None, tid=None, global_id=None):
        """Тестовая функция для получения команд."""
        if tag and tid:
            test_db = {
                ('deploy', 1): 'systemctl restart nginx',
                ('deploy', 2): 'nginx -t',
                ('deploy', 3): 'systemctl reload nginx',
                ('test', 1): 'python -m pytest',
            }
            return test_db.get((tag, tid))
        elif global_id is not None:
            test_db = {
                1: 'systemctl restart nginx',
                2: 'nginx -t',
                3: 'systemctl reload nginx',
            }
            return test_db.get(global_id)
        return None

    parser = CommandParser()

    # Тесты
    test_cases = [
        '!deploy[2]',
        '!deploy[2] && !deploy[1]',
        '!! deploy[2] && deploy[1]',
        '!1 && !2',
        '!! 1&&2',
    ]

    print("=== Command Parser Tests ===\n")

    for test_cmd in test_cases:
        print(f"Input: {test_cmd}")
        tokens = parser.parse(test_cmd)
        print(f"Tokens: {tokens}")

        assembled = parser.assemble_command(tokens, test_get_command)
        print(f"Assembled: {assembled}")
        print()
