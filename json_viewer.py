"""
JSON Viewer Module

Provides modal screen for viewing JSON data as interactive tree structure.
Supports jq path copying and navigation.
"""

from textual.screen import ModalScreen
from textual.widgets import Tree, Header, Footer
from textual.app import ComposeResult
from rich.text import Text
from rich.highlighter import ReprHighlighter
import pyperclip


class JSONViewer(ModalScreen):
    """
    Modal screen для просмотра JSON в виде дерева.

    Позволяет:
    - Просматривать JSON структуру в виде дерева
    - Выбирать элементы и копировать jq-путь по Enter
    - Закрывать по Escape или q
    """

    BINDINGS = [
        ("escape", "close_screen", "Close"),
        ("q", "close_screen", "Close"),
        ("up", "cursor_up", "Previous node"),
        ("down", "cursor_down", "Next node"),
        ("left", "cursor_parent", "Parent node"),
        ("right", "cursor_child", "First child"),
        ("space", "toggle_expand", "Expand/Collapse"),
        ("enter", "select_node", "Copy jq path"),
    ]

    def action_cursor_up(self) -> None:
        """Переместить курсор на предыдущий узел."""
        tree = self.query_one(Tree)
        tree.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Переместить курсор на следующий узел."""
        tree = self.query_one(Tree)
        tree.action_cursor_down()

    def action_cursor_parent(self) -> None:
        """Перейти к родительскому узлу."""
        tree = self.query_one(Tree)
        tree.action_cursor_parent()

    def action_cursor_child(self) -> None:
        """Перейти к первому дочернему узлу."""
        tree = self.query_one(Tree)
        cursor = tree.cursor_node
        if cursor:
            # Листовой узел - переходим к следующему соседу
            if not cursor.allow_expand:
                tree.action_cursor_next_sibling()
                return

            # Если узел еще не загружен, загружаем детей
            if hasattr(cursor, "_lazy_data"):
                self._load_children(cursor, cursor._lazy_data, cursor._jq_path)
                delattr(cursor, "_lazy_data")

            # Раскрываем узел если свернут
            if not cursor.is_expanded:
                cursor.expand()

            # Переходим к первому потомку
            if cursor.children:
                first_child = cursor.children[0]
                if not hasattr(first_child, "_is_placeholder"):
                    tree.cursor = first_child

    def action_toggle_expand(self) -> None:
        """Переключает состояние раскрытия текущего узла."""
        tree = self.query_one(Tree)
        if tree.cursor_node:
            cursor = tree.cursor_node
            if cursor.is_expanded:
                cursor.collapse()
            else:
                # Если узел еще не загружен, загружаем детей перед раскрытием
                if hasattr(cursor, "_lazy_data"):
                    self._load_children(cursor, cursor._lazy_data, cursor._jq_path)
                    delattr(cursor, "_lazy_data")
                cursor.expand()

    def action_select_node(self) -> None:
        """Выбирает текущий узел и копирует jq-путь."""
        tree = self.query_one(Tree)
        if tree.cursor_node:
            # Эмулируем событие выбора узла
            class FakeEvent:
                def __init__(self, node):
                    self.node = node

            self.on_tree_node_selected(FakeEvent(tree.cursor_node))

    def __init__(self, json_data: dict, **kwargs):
        """
        Инициализация JSON viewer.

        Args:
            json_data: Распаршенные JSON данные (dict/list)
        """
        super().__init__(**kwargs)
        self.json_data = json_data
        self.highlighter = ReprHighlighter()

    def compose(self) -> ComposeResult:
        """Создание UI."""
        yield Tree("JSON Root")

    def on_mount(self) -> None:
        """Загрузка JSON в дерево при открытии."""
        tree = self.query_one(Tree)
        # Ленивая загрузка - только первый уровень
        self._add_json_to_node(tree.root, self.json_data, [])
        # Вручную загружаем первый уровень (для root)
        if hasattr(tree.root, "_lazy_data"):
            self._load_children(tree.root, tree.root._lazy_data, tree.root._jq_path)
            delattr(tree.root, "_lazy_data")
        # Раскрываем корневой узел чтобы показать первый уровень
        tree.root.expand()
        tree.focus()  # Устанавливаем фокус на дерево для работы навигации

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Загружает дочерние элементы при раскрытии узла (ленивая загрузка)."""
        node = event.node
        # Загружаем детей только если есть _lazy_data (еще не загружены)
        if hasattr(node, "_lazy_data") and node._lazy_data is not None:
            self._load_children(node, node._lazy_data, node._jq_path)
            # После загрузки удаляем _lazy_data (это маркер что дети загружены)
            delattr(node, "_lazy_data")

    def _add_json_to_node(self, node, data, path_parts: list) -> None:
        """
        Добавляет JSON данные в узел дерева (без рекурсии для вложенных структур).

        Args:
            node: Узел дерева
            data: JSON данные
            path_parts: Части пути к текущему узлу (для генерации jq-пути)
        """
        if isinstance(data, dict):
            if not path_parts:  # Корневой узел
                node.set_label(Text.from_markup(f"{{}} [bold]JSON Root[/bold] ({len(data)} keys)"))
                node._jq_path = []  # Пустой путь для корня
            else:
                node.set_label(Text.from_markup(f"{{}} [bold]{path_parts[-1]}[/bold] ({len(data)} keys)"))
                # Важно: сохраняем jq_path для вложенных узлов!
                node._jq_path = path_parts

            # Сохраняем данные для ленивой загрузки (НЕ устанавливаем _lazy_loaded)
            node._lazy_data = data
            # НЕ устанавливаем node._lazy_loaded - проверка будет через hasattr

            # Добавляем пустой placeholder для индикатора раскрытия
            placeholder = node.add("...")
            placeholder._is_placeholder = True

        elif isinstance(data, list):
            if not path_parts:  # Корневой узел
                node.set_label(Text.from_markup(f"[] [bold]JSON Root[/bold] ({len(data)} items)"))
                node._jq_path = []  # Пустой путь для корня
            else:
                node.set_label(Text.from_markup(f"[] [bold]{path_parts[-1]}[/bold] ({len(data)} items)"))
                # Важно: сохраняем jq_path для вложенных узлов!
                node._jq_path = path_parts

            # Сохраняем данные для ленивой загрузки (НЕ устанавливаем _lazy_loaded)
            node._lazy_data = data
            # НЕ устанавливаем node._lazy_loaded - проверка будет через hasattr

            # Добавляем пустой placeholder для индикатора раскрытия
            placeholder = node.add("...")
            placeholder._is_placeholder = True

        else:
            # Листовой узел (значение) - загружаем сразу
            node.allow_expand = False
            # НЕ устанавливаем _lazy_loaded для листовых узлов

            if path_parts:
                # Формируем метку с именем и значением
                label = Text.assemble(
                    Text.from_markup(f"[b]{path_parts[-1]}[/b]="),
                    self.highlighter(repr(data))
                )
                node.set_label(label)
                # Сохраняем jq-путь для этого узла
                node._jq_path = path_parts
            else:
                # Корневое скалярное значение
                node.set_label(Text.from_markup(repr(data)))
                node._jq_path = []  # Пустой путь для корня

    def _load_children(self, node, data, path_parts: list) -> None:
        """
        Загружает дочерние элементы для узла (вызывается при раскрытии).

        Args:
            node: Родительский узел
            data: JSON данные
            path_parts: Части пути к текущему узлу
        """
        # Убедимся что path_parts не None
        if path_parts is None:
            path_parts = []

        # Удаляем placeholder если есть
        for child in list(node.children):
            if hasattr(child, "_is_placeholder"):
                child.remove()

        if isinstance(data, dict):
            for key, value in data.items():
                new_node = node.add("")
                # Проверяем, является ли ключ валидным идентификатором
                if str(key).isidentifier():
                    jq_part = f".{key}"
                else:
                    import json
                    jq_part = f"[{json.dumps(key)}]"
                new_node._jq_path = path_parts + [jq_part] if path_parts else [jq_part]
                # Рекурсивно добавляем только метку, дети загрузятся при раскрытии
                self._add_json_to_node(new_node, value, new_node._jq_path)

        elif isinstance(data, list):
            for index, value in enumerate(data):
                new_node = node.add("")
                new_node._jq_path = path_parts + [f"[{index}]"] if path_parts else [f"[{index}]"]
                self._add_json_to_node(new_node, value, new_node._jq_path)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """
        Обработчик выбора узла дерева (Enter или двойной клик).
        Копирует jq-путь выбранного узла и закрывает viewer.
        """
        node = event.node
        if hasattr(node, "_jq_path"):
            # Генерируем jq-путь
            jq_path = "".join(node._jq_path)

            # Добавляем ведущую точку если путь не пустой
            if jq_path and not jq_path.startswith("."):
                jq_path = "." + jq_path
            elif not jq_path:
                jq_path = "."

            # Отладка: записываем в файл
            with open('/tmp/jq_path_debug.log', 'a') as f:
                f.write(f"jq_path: {repr(jq_path)}\n")

            # Возвращаемся в основное приложение
            self.app.pop_screen()

            # Добавляем блок с jq-путем в основной фрейм
            if hasattr(self.app, 'add_block'):
                # Импортируем InfoBlock здесь, чтобы избежать циклического импорта
                from app import InfoBlock

                # Показываем путь в блоке (без кавычек для читаемости)
                self.app.add_block(InfoBlock(f"[bold]jq path:[/bold] {jq_path}"))

                # Копируем в буфер обмена с одинарными кавычками для удобства использования в bash
                try:
                    # Оборачиваем в одинарные кавычки для прямого использования в bash
                    clipboard_path = f"'{jq_path}'"
                    pyperclip.copy(clipboard_path)
                    self.app.sub_title = f"jq path copied: {clipboard_path}"

                    # Отладка: проверяем что скопировано
                    import pyperclip
                    clipboard_content = pyperclip.paste()
                    with open('/tmp/jq_path_debug.log', 'a') as f:
                        f.write(f"jq_path: {repr(jq_path)}\n")
                        f.write(f"clipboard: {repr(clipboard_content)}\n")
                except Exception as e:
                    with open('/tmp/jq_path_debug.log', 'a') as f:
                        f.write(f"error: {e}\n")

    def action_close_screen(self) -> None:
        """Закрывает текущий экран."""
        self.app.pop_screen()
