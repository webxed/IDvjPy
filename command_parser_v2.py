"""
command_parser_v2.py - Упрощенный парсер команд с поддержкой ссылок.

Использует детерминированный подход вместо pyparsing для надежности.

v1.1.9-experimental - Простая и надежная реализация.
"""

from typing import List, Tuple, Optional, Callable
import re


class CommandToken:
    """Токен команды - ссылка, оператор или текст."""

    def __init__(self, token_type: str, value: str,
                 tag: Optional[str] = None,
                 tid: Optional[int] = None,
                 global_id: Optional[int] = None):
        self.type = token_type  # 'tag_ref', 'global_ref', 'operator', 'text', 'double_bang'
        self.value = value
        self.tag = tag
        self.tid = tid
        self.global_id = global_id

    def __repr__(self):
        if self.type == 'tag_ref':
            return f"TagRef({self.tag}[{self.tid}])"
        elif self.type == 'global_ref':
            return f"GlobalRef(!{self.global_id})"
        elif self.type == 'operator':
            return f"Op('{self.value}')"
        elif self.type == 'text':
            return f"Text('{self.value}')"
        elif self.type == 'double_bang':
            return f"DoubleBang(!!)"
        return f"Token({self.type}, {self.value})"


class CommandParser:
    """
    Парсер команд с поддержкой ссылок на другие команды.

    Использует детерминированный подход для разбора:
    1. Сначала находит все специальные токены (!tag[tid], !ID, !!)
    2. Затем извлекает операторы между ними
    3. Остальное считает обычным текстом
    """

    # Регулярные выражения для распознавания токенов
    TAG_REF_PATTERN = r'!([a-zA-Z_0-9]+)\[(\d+)\]'
    GLOBAL_REF_PATTERN = r'!(\d+)'
    DOUBLE_BANG_PATTERN = r'^!!\s+'

    # Операторы shell
    OPERATORS = {'&&', '||', ';', '&', '|'}

    def parse(self, command: str) -> List[CommandToken]:
        """
        Парсит команду и возвращает список токенов.

        Args:
            command: Строка команды для парсинга

        Returns:
            Список токенов (CommandToken)
        """
        tokens = []
        command = command.strip()

        if not command:
            return tokens

        pos = 0
        has_double_bang = False

        # Шаг 1: Проверяем !!
        double_bang_match = re.match(self.DOUBLE_BANG_PATTERN, command)
        if double_bang_match:
            tokens.append(CommandToken('double_bang', '!!'))
            pos = double_bang_match.end()
            has_double_bang = True

        # Шаг 2: Парсим остаток команды
        while pos < len(command):
            # Пропускаем пробелы
            while pos < len(command) and command[pos].isspace():
                pos += 1

            if pos >= len(command):
                break

            # Проверяем специальные токены в порядке приоритета
            # 1. !tag[tid] - но только если не после !!
            tag_match = re.match(self.TAG_REF_PATTERN, command[pos:])
            if tag_match and not has_double_bang:
                tag = tag_match.group(1)
                tid = int(tag_match.group(2))
                tokens.append(CommandToken('tag_ref', tag_match.group(0),
                                         tag=tag, tid=tid))
                pos += len(tag_match.group(0))
                continue

            # 2. tag[tid] - без ! (для !! команд)
            tag_no_bang = re.match(r'([a-zA-Z_0-9]+)\[(\d+)\]', command[pos:])
            if tag_no_bang and has_double_bang:
                tag = tag_no_bang.group(1)
                tid = int(tag_no_bang.group(2))
                tokens.append(CommandToken('tag_ref', f"!{tag_no_bang.group(0)}",
                                         tag=tag, tid=tid))
                pos += len(tag_no_bang.group(0))
                continue

            # 3. !ID (но не !!)
            global_match = re.match(self.GLOBAL_REF_PATTERN, command[pos:])
            if global_match and not (pos == 0 and command.startswith('!!')) and not has_double_bang:
                global_id = int(global_match.group(1))
                tokens.append(CommandToken('global_ref', global_match.group(0),
                                         global_id=global_id))
                pos += len(global_match.group(0))
                continue

            # 4. ID - число без ! (для !! команд)
            id_no_bang = re.match(r'(\d+)', command[pos:])
            if id_no_bang and has_double_bang:
                global_id = int(id_no_bang.group(1))
                tokens.append(CommandToken('global_ref', f"!{id_no_bang.group(0)}",
                                         global_id=global_id))
                pos += len(id_no_bang.group(0))
                continue

            # 5. Оператор
            operator_found = None
            for op in sorted(self.OPERATORS, key=len, reverse=True):
                if command[pos:].startswith(op):
                    operator_found = op
                    pos += len(op)
                    break

            if operator_found:
                tokens.append(CommandToken('operator', operator_found))
                continue

            # 6. Обычный текст
            text_end = pos
            while text_end < len(command):
                char = command[text_end]
                if char in '!&|;':
                    break
                if char.isspace() and text_end + 1 < len(command):
                    next_char = command[text_end + 1]
                    if next_char in '!&|;':
                        break
                text_end += 1

            if text_end > pos:
                text = command[pos:text_end].strip()
                if text:
                    tokens.append(CommandToken('text', text))
                pos = text_end
            else:
                pos += 1

        return tokens

    def assemble_command(self, tokens: List[CommandToken],
                        get_command_fn: Callable) -> Optional[str]:
        """
        Собирает команду из токенов, раскрывая ссылки.

        Args:
            tokens: Список токенов от parse()
            get_command_fn: Функция для получения команды по ссылке
                           Принимает (tag=..., tid=...) или (global_id=...,)
                           Возвращает текст команды или None

        Returns:
            Собранная команда или None при ошибке
        """
        if not tokens:
            return None

        # Если есть !!, используем специальную сборку
        has_double_bang = any(t.type == 'double_bang' for t in tokens)

        if has_double_bang:
            return self._assemble_double_bang(tokens, get_command_fn)
        else:
            return self._assemble_normal(tokens, get_command_fn)

    def _assemble_normal(self, tokens: List[CommandToken],
                        get_command_fn: Callable) -> Optional[str]:
        """Собирает обычную команду (без !!)."""
        result_parts = []
        last_token_was_operator = False

        for token in tokens:
            if token.type == 'tag_ref':
                cmd_text = get_command_fn(tag=token.tag, tid=token.tid)
                if cmd_text is None:
                    return None
                if result_parts and not last_token_was_operator:
                    result_parts.append(' ')
                result_parts.append(cmd_text)
                last_token_was_operator = False

            elif token.type == 'global_ref':
                cmd_text = get_command_fn(global_id=token.global_id)
                if cmd_text is None:
                    return None
                if result_parts and not last_token_was_operator:
                    result_parts.append(' ')
                result_parts.append(cmd_text)
                last_token_was_operator = False

            elif token.type == 'operator':
                result_parts.append(f' {token.value} ')
                last_token_was_operator = True

            elif token.type == 'text':
                if result_parts and not last_token_was_operator:
                    result_parts.append(' ')
                result_parts.append(token.value)
                last_token_was_operator = False

            elif token.type == 'double_bang':
                # Не должно быть в обычной команде
                continue

        return ''.join(result_parts).strip()

    def _assemble_double_bang(self, tokens: List[CommandToken],
                            get_command_fn: Callable) -> Optional[str]:
        """Собирает команду с !!."""
        # Удаляем токен !! и собираем остальные
        filtered_tokens = [t for t in tokens if t.type != 'double_bang']
        return self._assemble_normal(filtered_tokens, get_command_fn)


# Тестирование модуля
if __name__ == '__main__':
    def test_get_command(**kwargs) -> Optional[str]:
        """Тестовая функция для получения команд."""
        if 'tag' in kwargs and 'tid' in kwargs:
            test_db = {
                ('deploy', 1): 'systemctl restart nginx',
                ('deploy', 2): 'nginx -t',
                ('deploy', 3): 'systemctl reload nginx',
                ('test', 1): 'python -m pytest',
            }
            return test_db.get((kwargs['tag'], kwargs['tid']))
        elif 'global_id' in kwargs:
            test_db = {
                1: 'systemctl restart nginx',
                2: 'nginx -t',
                3: 'systemctl reload nginx',
            }
            return test_db.get(kwargs['global_id'])
        return None

    parser = CommandParser()

    # Тесты
    test_cases = [
        '!deploy[2]',
        '!deploy[2] && !deploy[1]',
        '!! deploy[2] && deploy[1]',
        '!1 && !2',
        '!! 1&&2',
        '!deploy[2]; !deploy[3]',
        'ls -la && echo "test"',
    ]

    print("=== Command Parser v2 Tests ===\n")

    for test_cmd in test_cases:
        print(f"Input: {test_cmd}")
        tokens = parser.parse(test_cmd)
        print(f"Tokens: {tokens}")

        assembled = parser.assemble_command(tokens, test_get_command)
        print(f"Assembled: {assembled}")
        print(f"Success: {assembled is not None}\n")
        print("-" * 60)
