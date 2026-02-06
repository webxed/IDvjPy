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
        ("up", "tree.cursor_up", "Previous node"),
        ("down", "tree.cursor_down", "Next node"),
        ("left", "tree.cursor_parent", "Parent node"),
        ("right", "tree.cursor_child", "First child"),
        ("space", "toggle_expand", "Expand/Collapse"),
        ("enter", "select_node", "Copy jq path"),
    ]

    def action_toggle_expand(self) -> None:
        """Переключает состояние раскрытия текущего узла."""
        tree = self.query_one(Tree)
        if tree.cursor_node:
            if tree.cursor_node.is_expanded:
                tree.cursor_node.collapse()
            else:
                tree.cursor_node.expand()

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
        yield Header()
        yield Tree("JSON Root")
        yield Footer()

    def on_mount(self) -> None:
        """Загрузка JSON в дерево при открытии."""
        tree = self.query_one(Tree)
        tree.root.expand()
        self._add_json_to_node(tree.root, self.json_data, [])

    def _add_json_to_node(self, node, data, path_parts: list) -> None:
        """
        Рекурсивно добавляет JSON данные в узел дерева.

        Args:
            node: Узел дерева
            data: JSON данные
            path_parts: Части пути к текущему узлу (для генерации jq-пути)
        """
        if isinstance(data, dict):
            if not path_parts:  # Корневой узел
                node.set_label(Text("{} [bold]JSON Root[/bold]"))
            else:
                node.set_label(Text(f"{{}} [bold]{path_parts[-1]}[/bold]"))

            for key, value in data.items():
                new_node = node.add("")
                new_node._jq_path = path_parts + [f".{key}"] if path_parts else [f".{key}"]
                self._add_json_to_node(new_node, value, new_node._jq_path)

        elif isinstance(data, list):
            if not path_parts:  # Корневой узел
                node.set_label(Text("[] [bold]JSON Root[/bold]"))
            else:
                node.set_label(Text(f"[] [bold]{path_parts[-1]}[/bold]"))

            for index, value in enumerate(data):
                new_node = node.add("")
                new_node._jq_path = path_parts + [f"[{index}]"] if path_parts else [f"[{index}]"]
                self._add_json_to_node(new_node, value, new_node._jq_path)

        else:
            # Листовой узел (значение)
            node.allow_expand = False

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
                node.set_label(Text(repr(data)))
                node._jq_path = ["."]

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """
        Обработчик выбора узла дерева (Enter или двойной клик).
        Копирует jq-путь выбранного узла и закрывает viewer.
        """
        node = event.node
        if hasattr(node, "_jq_path"):
            # Генерируем jq-путь
            jq_path = "".join(node._jq_path)

            # Убираем ведущую точку если есть (для корректного jq)
            if jq_path.startswith("."):
                jq_path = "." + jq_path[1:] if jq_path != "." else "."

            # Возвращаемся в основное приложение
            self.app.pop_screen()

            # Добавляем блок с jq-путем в основной фрейм
            if hasattr(self.app, 'add_block'):
                # Импортируем InfoBlock здесь, чтобы избежать циклического импорта
                from app import InfoBlock
                self.app.add_block(InfoBlock(f"[bold]jq path:[/bold] {jq_path}"))
                # Также копируем в буфер обмена для удобства
                try:
                    pyperclip.copy(jq_path)
                    self.app.sub_title = f"jq path copied: {jq_path}"
                    self.app.set_timer(3, self.app.clear_subtitle)
                except Exception:
                    pass

    def action_close_screen(self) -> None:
        """Закрывает текущий экран."""
        self.app.pop_screen()
