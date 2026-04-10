"""
JSON Viewer Module

Provides modal screen for viewing JSON data as interactive tree structure.
Supports jq path copying, filtering, and match navigation.
"""

import json
import os
from typing import Any, List

import pyperclip
from rich.highlighter import ReprHighlighter
from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Tree


class JSONViewer(ModalScreen):
    """
    Modal screen для просмотра JSON в виде дерева.

    Позволяет:
    - Просматривать JSON структуру в виде дерева
    - Фильтровать по ключам, значениям и jq-path
    - Переходить по совпадениям (next/prev)
    - Выбирать элементы и копировать jq-путь по Enter
    - Закрывать по Escape или q
    """

    BINDINGS = [
        ("escape", "close_screen", "Close"),
        ("q", "close_screen", "Close"),
        ("/", "focus_search", "Search"),
        ("ctrl+f", "focus_search", "Search"),
        ("f6", "next_match", "Next match"),
        ("shift+f6", "prev_match", "Prev match"),
        ("n", "next_match", "Next match"),
        ("N", "prev_match", "Prev match"),
        ("up", "cursor_up", "Previous node"),
        ("down", "cursor_down", "Next node"),
        ("left", "cursor_parent", "Parent node"),
        ("right", "cursor_child", "First child"),
        ("space", "toggle_expand", "Expand/Collapse"),
        ("enter", "select_node", "Copy jq path"),
    ]

    def __init__(self, json_data: dict, **kwargs):
        super().__init__(**kwargs)
        self.json_data = json_data
        self.highlighter = ReprHighlighter()
        self.search_query = ""
        self.match_nodes: List[Any] = []
        self.current_match_index = -1
        self.total_nodes = 0

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search keys, values, jq path...", id="json-search")
        yield Tree("JSON Root")

    def on_mount(self) -> None:
        search_input = self.query_one("#json-search", Input)
        search_input.value = ""
        self._render_tree()
        self.query_one(Tree).focus()

        if self.total_nodes > 5000:
            self.app.sub_title = (
                f"Large JSON: {self.total_nodes} nodes loaded. "
                "All branches are expanded."
            )
        else:
            self.app.sub_title = "JSON viewer opened. Press / to search."

    def _json_to_display_text(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        return repr(data)

    def _make_node_label(self, key_name: str, data: Any) -> Text:
        if isinstance(data, dict):
            return Text.from_markup(f"{{}} [bold]{key_name}[/bold] ({len(data)} keys)")
        if isinstance(data, list):
            return Text.from_markup(f"[] [bold]{key_name}[/bold] ({len(data)} items)")
        return Text.assemble(
            Text.from_markup(f"[b]{key_name}[/b]="),
            self.highlighter(repr(data)),
        )

    def _path_parts_to_jq_path(self, path_parts: List[str]) -> str:
        jq_path = "".join(path_parts)
        if jq_path and not jq_path.startswith("."):
            jq_path = "." + jq_path
        elif not jq_path:
            jq_path = "."
        return jq_path

    def _matches_query(self, key_name: str, data: Any, jq_path: str) -> bool:
        if not self.search_query:
            return True
        blob = f"{key_name} {self._json_to_display_text(data)} {jq_path}".lower()
        return self.search_query in blob

    def _collect_children(self, data: Any, path_parts: List[str]) -> List[tuple]:
        children: List[tuple] = []
        if isinstance(data, dict):
            for child_key, child_value in data.items():
                if str(child_key).isidentifier():
                    jq_part = f".{child_key}"
                else:
                    jq_part = f"[{json.dumps(child_key)}]"
                child_path = path_parts + [jq_part] if path_parts else [jq_part]
                children.append((str(child_key), child_value, child_path))
        elif isinstance(data, list):
            for idx, child_value in enumerate(data):
                child_path = path_parts + [f"[{idx}]"] if path_parts else [f"[{idx}]"]
                children.append((f"[{idx}]", child_value, child_path))
        return children

    def _node_or_descendant_matches(self, key_name: str, data: Any, path_parts: List[str]) -> bool:
        jq_path = self._path_parts_to_jq_path(path_parts)
        if self._matches_query(key_name, data, jq_path):
            return True
        for child_key, child_value, child_path in self._collect_children(data, path_parts):
            if self._node_or_descendant_matches(child_key, child_value, child_path):
                return True
        return False

    def _build_tree_filtered(self, parent_node: Any, key_name: str, data: Any, path_parts: List[str]) -> None:
        if self.search_query and not self._node_or_descendant_matches(key_name, data, path_parts):
            return

        node = parent_node.add("")
        node.set_label(self._make_node_label(key_name, data))
        node._jq_path = path_parts
        node._jq_path_str = self._path_parts_to_jq_path(path_parts)
        self.total_nodes += 1

        direct_match = self._matches_query(key_name, data, node._jq_path_str)
        if self.search_query and direct_match:
            self.match_nodes.append(node)

        for child_key, child_value, child_path in self._collect_children(data, path_parts):
            self._build_tree_filtered(node, child_key, child_value, child_path)

        if isinstance(data, (dict, list)):
            node.expand()
        else:
            node.allow_expand = False

    def _render_tree(self) -> None:
        tree = self.query_one(Tree)
        tree.clear()
        self.match_nodes = []
        self.current_match_index = -1
        self.total_nodes = 0

        root = tree.root
        self._build_tree_filtered(root, "JSON Root", self.json_data, [])
        root.expand()

        if root.children:
            tree.cursor = root.children[0]

        if self.match_nodes:
            self.current_match_index = 0
            tree.cursor = self.match_nodes[0]
            self.app.sub_title = f"Search matches: 1/{len(self.match_nodes)}"
        elif self.search_query:
            self.app.sub_title = "Search matches: 0/0"

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "json-search":
            return
        self.search_query = event.value.strip().lower()
        self._render_tree()

    def action_focus_search(self) -> None:
        search_input = self.query_one("#json-search", Input)
        search_input.focus()
        search_input.cursor_position = len(search_input.value)

    def action_next_match(self) -> None:
        if not self.match_nodes:
            self.app.sub_title = "Search matches: 0/0"
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.match_nodes)
        self.query_one(Tree).cursor = self.match_nodes[self.current_match_index]
        self.app.sub_title = f"Search matches: {self.current_match_index + 1}/{len(self.match_nodes)}"

    def action_prev_match(self) -> None:
        if not self.match_nodes:
            self.app.sub_title = "Search matches: 0/0"
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.match_nodes)
        self.query_one(Tree).cursor = self.match_nodes[self.current_match_index]
        self.app.sub_title = f"Search matches: {self.current_match_index + 1}/{len(self.match_nodes)}"

    def action_cursor_up(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        self.query_one(Tree).action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        self.query_one(Tree).action_cursor_down()

    def action_cursor_parent(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        self.query_one(Tree).action_cursor_parent()

    def action_cursor_child(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        self.query_one(Tree).action_cursor_child()

    def action_toggle_expand(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        tree = self.query_one(Tree)
        if tree.cursor_node:
            if tree.cursor_node.is_expanded:
                tree.cursor_node.collapse()
            else:
                tree.cursor_node.expand()

    def action_select_node(self) -> None:
        if self.query_one("#json-search", Input).has_focus:
            return
        tree = self.query_one(Tree)
        if tree.cursor_node:
            class FakeEvent:
                def __init__(self, node):
                    self.node = node

            self.on_tree_node_selected(FakeEvent(tree.cursor_node))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if hasattr(node, "_jq_path"):
            jq_path = self._path_parts_to_jq_path(node._jq_path)

            self.app.pop_screen()

            if hasattr(self.app, "add_block"):
                from app import InfoBlock

                self.app.add_block(InfoBlock(f"[bold]jq path:[/bold] {jq_path}"))

                # Делаем путь доступным в шаблонах команд как $JSON.
                if hasattr(self.app, "local_env"):
                    self.app.local_env["JSON"] = jq_path
                os.environ["JSON"] = jq_path

                try:
                    clipboard_path = f"'{jq_path}'"
                    pyperclip.copy(clipboard_path)
                    self.app.sub_title = f"jq path copied: {clipboard_path}; $JSON set"
                except Exception:
                    pass

    def action_close_screen(self) -> None:
        self.app.pop_screen()
