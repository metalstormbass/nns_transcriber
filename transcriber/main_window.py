import json
import re
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_TITLE


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 900)
        self.setMinimumSize(960, 640)

        self.working_dir = Path.home()
        self.library_path = self.working_dir / ".nns_transcriber_library.json"
        self.projects_dir = self.working_dir
        self.song_library = []
        self.visible_library_indices = []

        self.current_library_entry = None
        self.current_song_title = ""
        self.project_path = None
        self._loading_project = False
        self._formatting_chart_text = False
        self._splitter_initialized = False
        self._working_dir_initialized = False
        self._context_block_number = -1
        self._context_pos_in_block = 0
        self._handling_undo_redo = False
        self._auto_format_enabled = True
        self._reader_mode = False
        self._reader_prev_sizes = [354, 802, 204]

        self.song_title_input = QLineEdit()
        self.song_title_input.setPlaceholderText("Song title")
        self.song_key_input = QLineEdit()
        self.song_key_input.setPlaceholderText("Key (e.g. C, Eb, F#m)")
        self.song_key_input.setMaximumWidth(140)
        self.remote_url_input = QLineEdit()
        self.remote_url_input.setPlaceholderText("YouTube or Spotify link")
        self.open_remote_btn = QPushButton("Open Link")
        self.export_btn = QPushButton("Export Rendered")
        self.reader_mode_btn = QPushButton("Reader Mode")
        self.reader_mode_btn.setCheckable(True)
        self.auto_format_btn = QPushButton("Auto Format")
        self.auto_format_btn.setCheckable(True)
        self.auto_format_btn.setChecked(True)

        self.markdown_editor = QTextEdit()
        self.markdown_editor.setPlaceholderText("Write markdown chart here")
        editor_font = self.markdown_editor.font()
        editor_font.setFamily("Menlo")
        editor_font.setPointSize(14)
        self.markdown_editor.setFont(editor_font)
        self.markdown_editor.setLineWrapMode(QTextEdit.NoWrap)
        self.markdown_editor.setReadOnly(True)

        self.markdown_preview = QTextEdit()
        self.markdown_preview.setReadOnly(True)

        self.library_list = QListWidget()
        self.library_add_btn = QPushButton("Add Song")
        self.library_remove_btn = QPushButton("Remove Song")
        self.include_subfolders_check = QCheckBox("Include subfolders")

        self.build_ui()
        self.bind_events()

        self.project_save_timer = QTimer(self)
        self.project_save_timer.setSingleShot(True)
        self.project_save_timer.timeout.connect(self.autosave_project)

        self.update_auto_format_button_style()

        self.set_chart_editable(False)
        self.update_preview()
        self.statusBar().showMessage("Chart utility ready. Choose a working directory.")

    def pick_working_directory(self) -> Path:
        # Use native folder picker for better responsiveness on macOS.
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose Working Directory",
            str(self.working_dir),
            QFileDialog.ShowDirsOnly,
        )
        if chosen:
            return Path(chosen)
        return self.working_dir

    def apply_working_directory(self, chosen: Path):
        self.working_dir = chosen
        self.library_path = self.working_dir / ".nns_transcriber_library.json"
        self.projects_dir = self.working_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.load_song_library()
        self.refresh_song_library_view()
        self.statusBar().showMessage(
            f"Chart utility ready. Working directory: {self.working_dir}"
        )

    def project_path_in_scope(self, project_path: str):
        if not project_path:
            return False
        try:
            parent = Path(project_path).resolve().parent
            work_dir = self.working_dir.resolve()
        except Exception:
            parent = Path(project_path).parent
            work_dir = self.working_dir

        if parent == work_dir:
            return True
        if not self.include_subfolders_check.isChecked():
            return False
        try:
            parent.relative_to(work_dir)
            return True
        except Exception:
            return False

    def initialize_working_directory(self):
        self.activateWindow()
        self.raise_()
        chosen = self.pick_working_directory()
        self.apply_working_directory(chosen)

    def open_working_directory(self):
        chosen = self.pick_working_directory()
        if not chosen:
            return
        if self.project_path:
            self.autosave_project()
        self.apply_working_directory(chosen)
        self.clear_current_song()

    def build_ui(self):
        metadata_row = QHBoxLayout()
        metadata_row.addWidget(QLabel("Title"))
        metadata_row.addWidget(self.song_title_input)
        metadata_row.addWidget(QLabel("Key"))
        metadata_row.addWidget(self.song_key_input)
        metadata_row.addWidget(QLabel("Link"))
        metadata_row.addWidget(self.remote_url_input)
        metadata_row.addWidget(self.open_remote_btn)
        metadata_row.addWidget(self.export_btn)
        metadata_row.addWidget(self.reader_mode_btn)
        metadata_row.addWidget(self.auto_format_btn)

        self.metadata_widget = QWidget()
        self.metadata_widget.setLayout(metadata_row)
        self.metadata_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        library_box = QVBoxLayout()
        library_box.addWidget(QLabel("Song Library"))
        library_box.addWidget(self.include_subfolders_check)
        library_box.addWidget(self.library_list)
        library_actions = QHBoxLayout()
        library_actions.addWidget(self.library_add_btn)
        library_actions.addWidget(self.library_remove_btn)
        library_actions.addStretch()
        library_box.addLayout(library_actions)
        library_panel = QWidget()
        library_panel.setLayout(library_box)
        self.library_panel = library_panel

        root = QSplitter(Qt.Horizontal)
        root.setChildrenCollapsible(False)
        root.addWidget(self.markdown_editor)
        root.addWidget(self.markdown_preview)
        root.addWidget(self.library_panel)
        root.setStretchFactor(0, 26)
        root.setStretchFactor(1, 59)
        root.setStretchFactor(2, 15)
        root.setSizes([354, 802, 204])
        self.root_splitter = root

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 6, 8, 8)
        container_layout.setSpacing(6)
        container_layout.addWidget(self.metadata_widget)
        container_layout.addWidget(root)
        container_layout.setStretch(0, 0)
        container_layout.setStretch(1, 1)
        self.setCentralWidget(container)

        file_menu = self.menuBar().addMenu("&File")
        add_action = QAction("Add Song", self)
        add_action.setShortcut(QKeySequence("Ctrl+N"))
        add_action.triggered.connect(self.add_link_song)
        file_menu.addAction(add_action)

        open_folder_action = QAction("Open Folder", self)
        open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_action.triggered.connect(self.open_working_directory)
        file_menu.addAction(open_folder_action)

        save_as_action = QAction("Save Project As", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)

        export_action = QAction("Export Rendered Chart", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_rendered_chart)
        file_menu.addAction(export_action)

        export_md_action = QAction("Export Markdown", self)
        export_md_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_md_action.triggered.connect(self.export_markdown)
        file_menu.addAction(export_md_action)

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.perform_undo)
        self.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.perform_redo)
        self.addAction(redo_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        view_menu = self.menuBar().addMenu("&View")
        self.reader_mode_action = QAction("Reader Mode", self)
        self.reader_mode_action.setCheckable(True)
        self.reader_mode_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.reader_mode_action.triggered.connect(self.toggle_reader_mode)
        view_menu.addAction(self.reader_mode_action)

        exit_reader_action = QAction("Exit Reader Mode", self)
        exit_reader_action.setShortcut(QKeySequence("Esc"))
        exit_reader_action.triggered.connect(self.exit_reader_mode)
        self.addAction(exit_reader_action)

    def perform_undo(self):
        focused = QApplication.focusWidget()
        if focused is None:
            return
        if hasattr(focused, "undo") and callable(getattr(focused, "undo")):
            self._handling_undo_redo = True
            focused.undo()
            self._handling_undo_redo = False
            return
        if hasattr(self.markdown_editor, "undo"):
            self._handling_undo_redo = True
            self.markdown_editor.undo()
            self._handling_undo_redo = False

    def perform_redo(self):
        focused = QApplication.focusWidget()
        if focused is None:
            return
        if hasattr(focused, "redo") and callable(getattr(focused, "redo")):
            self._handling_undo_redo = True
            focused.redo()
            self._handling_undo_redo = False
            return
        if hasattr(self.markdown_editor, "redo"):
            self._handling_undo_redo = True
            self.markdown_editor.redo()
            self._handling_undo_redo = False

    def bind_events(self):
        self.library_list.itemClicked.connect(self.open_selected_library_song)
        self.library_list.itemDoubleClicked.connect(self.open_selected_library_song)
        self.library_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.library_list.customContextMenuRequested.connect(self.show_library_context_menu)
        self.include_subfolders_check.toggled.connect(lambda _checked: self.refresh_song_library_view())
        self.library_add_btn.clicked.connect(self.add_link_song)
        self.library_remove_btn.clicked.connect(self.remove_selected_library_song)

        self.song_title_input.editingFinished.connect(self.on_metadata_changed)
        self.song_key_input.editingFinished.connect(self.on_metadata_changed)
        self.remote_url_input.editingFinished.connect(self.on_metadata_changed)
        self.song_title_input.textChanged.connect(self.on_metadata_changed)
        self.song_key_input.textChanged.connect(self.on_metadata_changed)
        self.remote_url_input.textChanged.connect(self.on_metadata_changed)
        self.markdown_editor.textChanged.connect(self.on_chart_text_changed)
        self.markdown_editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.markdown_editor.customContextMenuRequested.connect(self.show_editor_context_menu)

        self.open_remote_btn.clicked.connect(lambda: self.open_associated_url(self.remote_url_input.text().strip()))
        self.export_btn.clicked.connect(self.export_rendered_chart)
        self.reader_mode_btn.toggled.connect(self.toggle_reader_mode)
        self.auto_format_btn.toggled.connect(self.toggle_auto_format)

    def toggle_auto_format(self, enabled: bool):
        self._auto_format_enabled = bool(enabled)
        self.update_auto_format_button_style()
        self.statusBar().showMessage("Auto format enabled" if self._auto_format_enabled else "Auto format disabled")

    def update_auto_format_button_style(self):
        if self._auto_format_enabled:
            self.auto_format_btn.setStyleSheet(
                "QPushButton {"
                " background-color: #2d7f52;"
                " color: #ffffff;"
                " border: 1px solid #4aa270;"
                " border-radius: 4px;"
                " padding: 3px 10px;"
                "}"
            )
        else:
            self.auto_format_btn.setStyleSheet(
                "QPushButton {"
                " background-color: #4b4b4b;"
                " color: #d7d7d7;"
                " border: 1px solid #666666;"
                " border-radius: 4px;"
                " padding: 3px 10px;"
                "}"
            )

    def toggle_reader_mode(self, enabled: bool):
        enabled = bool(enabled)
        self._reader_mode = enabled

        # Keep button/menu states synchronized regardless of trigger source.
        if self.reader_mode_btn.isChecked() != enabled:
            self.reader_mode_btn.blockSignals(True)
            self.reader_mode_btn.setChecked(enabled)
            self.reader_mode_btn.blockSignals(False)
        if self.reader_mode_action.isChecked() != enabled:
            self.reader_mode_action.blockSignals(True)
            self.reader_mode_action.setChecked(enabled)
            self.reader_mode_action.blockSignals(False)

        if enabled:
            self._reader_prev_sizes = self.root_splitter.sizes()
            self.metadata_widget.show()
            self.markdown_editor.hide()
            self.library_panel.hide()
            self.root_splitter.setSizes([0, 1, 0])
            self.statusBar().showMessage("Reader Mode enabled")
            return

        self.metadata_widget.show()
        self.markdown_editor.show()
        self.library_panel.show()
        restore = self._reader_prev_sizes if self._reader_prev_sizes else [354, 802, 204]
        self.root_splitter.setSizes(restore)
        self.statusBar().showMessage("Edit Mode enabled")

    def exit_reader_mode(self):
        if self._reader_mode:
            self.toggle_reader_mode(False)

    def show_library_context_menu(self, pos):
        menu = QMenu(self)
        add_action = menu.addAction("Add Song")
        remove_action = menu.addAction("Remove Song")

        item = self.library_list.itemAt(pos)
        if item is not None:
            self.library_list.setCurrentItem(item)
        remove_action.setEnabled(self.library_list.currentRow() >= 0)

        selected_action = menu.exec(self.library_list.mapToGlobal(pos))
        if selected_action == add_action:
            self.add_link_song()
        elif selected_action == remove_action:
            self.remove_selected_library_song()

    def show_editor_context_menu(self, pos):
        context_cursor = self.markdown_editor.cursorForPosition(pos)
        self._context_block_number = context_cursor.blockNumber()
        self._context_pos_in_block = context_cursor.positionInBlock()
        menu = self.markdown_editor.createStandardContextMenu()
        add_rhythm_action = QAction("Add Rhythm Row Below", self)
        add_rhythm_action.setEnabled(not self.markdown_editor.isReadOnly())
        add_rhythm_action.triggered.connect(self.add_rhythm_row_below)
        actions = menu.actions()
        if actions:
            menu.insertAction(actions[0], add_rhythm_action)
            menu.insertSeparator(actions[0])
        else:
            menu.addAction(add_rhythm_action)
        menu.exec(self.markdown_editor.mapToGlobal(pos))

    def add_rhythm_row_below(self):
        document = self.markdown_editor.document()
        if self._context_block_number >= 0:
            block = document.findBlockByNumber(self._context_block_number)
        else:
            block = self.markdown_editor.textCursor().block()
        line = block.text()
        stripped = line.strip()

        if not (line.count("|") >= 2 and stripped.startswith("|") and stripped.endswith("|")):
            QMessageBox.information(
                self,
                "Select a bar row",
                "Right-click on a bar line first, then choose Add Rhythm Row Below.",
            )
            return

        raw_cells = line.split("|")[1:-1]
        if not raw_cells:
            return

        # Map the right-click position in the line to a bar-cell index.
        bar_positions = [i for i, ch in enumerate(line) if ch == "|"]
        target_cell_index = 0
        if len(bar_positions) >= 2:
            for i in range(len(bar_positions) - 1):
                left = bar_positions[i]
                right = bar_positions[i + 1]
                if left <= self._context_pos_in_block <= right:
                    target_cell_index = i
                    break
            else:
                target_cell_index = max(0, min(len(raw_cells) - 1, len(bar_positions) - 2))
        target_cell_index = max(0, min(target_cell_index, len(raw_cells) - 1))

        # Keep rhythm cells visually locked to the same bar widths.
        # Default each x to a quarter-note hit in the selected bar cell only.
        rhythm_cells = []
        for idx, cell in enumerate(raw_cells):
            width = max(3, len(cell))
            if idx == target_cell_index:
                rhythm_cells.append(" " + "x".ljust(max(1, width - 1)))
            else:
                rhythm_cells.append(" " * width)
        rhythm_line = "|" + "|".join(rhythm_cells) + "|"

        insert_cursor = QTextCursor(block)
        insert_cursor.movePosition(QTextCursor.EndOfBlock)
        insert_cursor.insertBlock()
        insert_cursor.insertText(rhythm_line)

        # Move cursor into the first rhythm cell to start entering shots quickly.
        insert_cursor.setPosition(insert_cursor.position() - len(rhythm_line) + 1)
        self.markdown_editor.setTextCursor(insert_cursor)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._working_dir_initialized:
            self._working_dir_initialized = True
            QTimer.singleShot(120, self.initialize_working_directory)
        if self._splitter_initialized:
            return
        total = max(1, self.root_splitter.width())
        left = int(total * 0.26)
        middle = int(total * 0.59)
        right = max(1, total - left - middle)
        self.root_splitter.setSizes([left, middle, right])
        self._splitter_initialized = True

    def load_song_library(self):
        if not self.library_path.exists():
            self.song_library = []
            return

        try:
            data = json.loads(self.library_path.read_text(encoding="utf-8"))
            self.song_library = self.normalize_library_data(data)
        except Exception:
            self.song_library = []

    def normalize_library_data(self, data):
        if not isinstance(data, list):
            return []

        out = []
        for idx, item in enumerate(data, start=1):
            if isinstance(item, str):
                title = Path(item).stem or f"Song {idx}"
                slug = self.slugify(title)
                out.append(
                    {
                        "title": title,
                        "song_key": "",
                        "playlist": "",
                        "remote_url": "",
                        "project_path": str(self.projects_dir / f"{slug}.mccp.json"),
                    }
                )
                continue

            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "") or "").strip() or f"Song {idx}"
            song_key = str(item.get("song_key", "") or "").strip()
            playlist = str(item.get("playlist", "") or "").strip()
            youtube_url = str(item.get("youtube_url", "") or "").strip()
            spotify_url = str(item.get("spotify_url", "") or "").strip()
            remote_url = str(item.get("remote_url", "") or "").strip()
            stream_url = str(item.get("stream_url", "") or "").strip()

            if not remote_url:
                if youtube_url:
                    remote_url = youtube_url
                elif spotify_url:
                    remote_url = spotify_url
                elif stream_url:
                    remote_url = stream_url

            project_path = str(item.get("project_path", "") or "").strip()
            if not project_path:
                slug = self.slugify(title)
                project_path = str(self.projects_dir / f"{slug}.mccp.json")

            out.append(
                {
                    "title": title,
                    "song_key": song_key,
                    "playlist": playlist,
                    "remote_url": remote_url,
                    "project_path": project_path,
                }
            )

        return out

    def save_song_library(self):
        try:
            self.library_path.write_text(json.dumps(self.song_library, indent=2), encoding="utf-8")
        except Exception as exc:
            self.statusBar().showMessage(f"Could not save song library: {exc}")

    def refresh_song_library_view(self):
        self.library_list.clear()
        self.visible_library_indices = []

        for idx, entry in enumerate(self.song_library):
            project_path = str(entry.get("project_path", "") or "").strip()
            if not self.project_path_in_scope(project_path):
                continue
            playlist = str(entry.get("playlist", "")).strip()
            title = str(entry.get("title", "Untitled Song"))
            prefix = f"[{playlist}] " if playlist else ""
            has_link = bool(str(entry.get("remote_url", "")).strip())
            suffix = "linked" if has_link else "no-link"
            self.visible_library_indices.append(idx)
            self.library_list.addItem(f"{prefix}{title} [{suffix}]")

    def remember_song(self, entry: dict):
        project_path = str(entry.get("project_path", ""))
        self.song_library = [e for e in self.song_library if str(e.get("project_path", "")) != project_path]
        self.song_library.insert(0, entry)
        self.song_library = self.song_library[:500]
        self.save_song_library()
        self.refresh_song_library_view()

    def slugify(self, text: str):
        return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower() or "song"

    def unique_project_path(self, slug: str):
        base = self.projects_dir / f"{slug}.mccp.json"
        if not base.exists():
            return base
        i = 2
        while True:
            candidate = self.projects_dir / f"{slug}_{i}.mccp.json"
            if not candidate.exists():
                return candidate
            i += 1

    def add_link_song(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Song")

        form = QFormLayout(dialog)
        title_input = QLineEdit(dialog)
        title_input.setPlaceholderText("Song title")
        key_input = QLineEdit(dialog)
        key_input.setPlaceholderText("C")
        key_input.setMaximumWidth(120)
        link_input = QLineEdit(dialog)
        link_input.setPlaceholderText("YouTube or Spotify URL (optional)")

        form.addRow("Title", title_input)
        form.addRow("Key", key_input)
        form.addRow("Link", link_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        title_input.setFocus()
        if dialog.exec() != QDialog.Accepted:
            return

        title = title_input.text().strip()
        if not title:
            QMessageBox.information(self, "Missing title", "Enter a song title.")
            return
        song_key = key_input.text().strip()
        remote_url = link_input.text().strip()

        slug = self.slugify(title)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        project_path = self.unique_project_path(slug)
        entry = {
            "title": title,
            "song_key": song_key.strip(),
            "playlist": "",
            "remote_url": remote_url.strip(),
            "project_path": str(project_path),
        }
        self.remember_song(entry)
        self.load_song_entry(entry)

    def open_selected_library_song(self, item):
        row = self.library_list.row(item)
        if row < 0 or row >= len(self.visible_library_indices):
            return
        idx = self.visible_library_indices[row]
        entry = self.song_library[idx]

        self.load_song_entry(entry)

    def load_song_entry(self, entry: dict):
        if self.project_path:
            self.autosave_project()

        self.current_library_entry = dict(entry)
        self.current_song_title = str(entry.get("title", "Untitled Song"))
        self.project_path = Path(str(entry.get("project_path", "")))

        self.song_title_input.setText(self.current_song_title)
        self.song_key_input.setText(str(entry.get("song_key", "") or ""))
        self.remote_url_input.setText(str(entry.get("remote_url", "") or ""))

        self.set_chart_editable(True)
        if self.project_path.exists():
            self.load_project_file(self.project_path)
        else:
            self.markdown_editor.blockSignals(True)
            self.markdown_editor.setPlainText(
                self.default_chart_template(
                    self.current_song_title,
                    self.song_key_input.text().strip(),
                )
            )
            self.markdown_editor.blockSignals(False)
            self.normalize_chart_spacing()
            self.update_preview()
            self.autosave_project()

        self.setWindowTitle(f"{APP_TITLE} - {self.current_song_title}")
        self.statusBar().showMessage(f"Loaded {self.current_song_title}")

    def remove_selected_library_song(self):
        row = self.library_list.currentRow()
        if row < 0 or row >= len(self.visible_library_indices):
            QMessageBox.information(self, "No song selected", "Select a library song to remove.")
            return

        idx = self.visible_library_indices[row]
        removed = self.song_library[idx]
        removed_project = str(removed.get("project_path", ""))

        del self.song_library[idx]
        self.save_song_library()
        self.refresh_song_library_view()

        current_project = str(self.project_path) if self.project_path else ""
        if removed_project and removed_project == current_project:
            self.clear_current_song()

    def clear_current_song(self):
        self.current_library_entry = None
        self.current_song_title = ""
        self.project_path = None

        self.song_title_input.clear()
        self.song_key_input.clear()
        self.remote_url_input.clear()
        self.markdown_editor.blockSignals(True)
        self.markdown_editor.setPlainText("")
        self.markdown_editor.blockSignals(False)

        self.set_chart_editable(False)
        self.update_preview()
        self.setWindowTitle(APP_TITLE)
        self.statusBar().showMessage("Ready for a new chart.")

    def set_chart_editable(self, editable: bool):
        self.song_title_input.setEnabled(editable)
        self.song_key_input.setEnabled(editable)
        self.remote_url_input.setEnabled(editable)
        self.open_remote_btn.setEnabled(editable)
        self.export_btn.setEnabled(editable)
        self.markdown_editor.setReadOnly(not editable)

    def default_chart_template(self, song_name: str, song_key: str = ""):
        key_text = song_key.strip() or "C"
        return (
            f"# {song_name}\n"
            f"**Key:** {key_text}\n\n"
            "```text\n"
            "[intro]\n"
            "(hook / pickup)\n"
            "| 1  |    |    |    |\n"
            "|    |    |    |    |\n\n"
            "[verse]\n"
            "(lyrics / idea)\n"
            "| 1  | 6- | 5  | 4  1 |\n"
            "| 1  | 6- | 5  | 4  1 |\n\n"
            "[chorus]\n"
            "(lyrics / idea)\n"
            "| 1  | 5  | 6- | 4    |\n"
            "| 1  | 5  | 4  | 1    |\n\n"
            "[bridge]\n"
            "(lyrics / idea)\n"
            "| 6- 5 | 1  | 4  1 | 5    |\n"
            "| 6- b7| 4 1| 5    | 5 7  |\n\n"
            "[outro]\n"
            "(ending)\n"
            "| 1  | 5  | 4  | 1    |\n"
            "|    |    |    |      |\n"
            "```\n"
        )

    def on_metadata_changed(self, *_args):
        if self._loading_project or not self.current_library_entry:
            return

        self.current_song_title = self.song_title_input.text().strip() or "Untitled Song"
        self.current_library_entry["title"] = self.current_song_title
        self.current_library_entry["song_key"] = self.song_key_input.text().strip()
        self.current_library_entry["remote_url"] = self.remote_url_input.text().strip()
        self.current_library_entry["project_path"] = str(self.project_path) if self.project_path else ""

        self.remember_song(dict(self.current_library_entry))
        self.setWindowTitle(f"{APP_TITLE} - {self.current_song_title}")
        self.schedule_project_save()

    def on_chart_text_changed(self):
        if self._loading_project:
            return

        if self._handling_undo_redo:
            self.update_preview()
            self.schedule_project_save()
            return

        # Apply table normalization immediately after each character edit when enabled.
        if self._auto_format_enabled:
            self.normalize_chart_spacing()
        self.update_preview()
        self.schedule_project_save()

    def normalize_chart_spacing(self):
        if self._formatting_chart_text:
            return

        text = self.markdown_editor.toPlainText()
        if not text:
            return

        lines = text.splitlines()
        changed = False

        parsed_rows = []
        widths_by_cols = {}
        for line in lines:
            first_bar = line.find("|")
            last_bar = line.rfind("|")
            if first_bar >= 0 and last_bar > first_bar:
                bar_chunk = line[first_bar : last_bar + 1]
                if bar_chunk.count("|") >= 2 and bar_chunk.startswith("|") and bar_chunk.endswith("|"):
                    cells = [cell.strip() for cell in bar_chunk.split("|")[1:-1]]
                    col_count = len(cells)
                    prefix = line[:first_bar]
                    suffix = line[last_bar + 1 :].strip()
                    parsed_rows.append((line, prefix, cells, col_count, suffix))
                    if col_count not in widths_by_cols:
                        widths_by_cols[col_count] = [3 for _ in range(col_count)]
                    widths = widths_by_cols[col_count]
                    for i, cell in enumerate(cells):
                        widths[i] = max(widths[i], len(cell), 3)
                    continue

            parsed_rows.append((line, None, None, 0, ""))

        out = []
        for original_line, prefix, cells, col_count, suffix in parsed_rows:
            if cells is None:
                out.append(original_line.rstrip())
                continue

            widths = widths_by_cols[col_count]
            normalized_bar = "|" + "|".join(f" {cell:<{widths[i]}} " for i, cell in enumerate(cells)) + "|"
            normalized = f"{prefix}{normalized_bar}"
            if suffix:
                normalized = f"{normalized} {suffix}"
            out.append(normalized)
            changed = changed or (normalized != original_line)

        normalized_text = "\n".join(out)
        if text.endswith("\n"):
            normalized_text += "\n"

        if changed:
            cursor = self.markdown_editor.textCursor()
            pos = cursor.position()
            self._formatting_chart_text = True
            self.markdown_editor.blockSignals(True)
            self.markdown_editor.setPlainText(normalized_text)
            self.markdown_editor.blockSignals(False)
            cursor = self.markdown_editor.textCursor()
            cursor.setPosition(min(pos, len(normalized_text)))
            self.markdown_editor.setTextCursor(cursor)
            self._formatting_chart_text = False

    def update_preview(self):
        self.markdown_preview.setHtml(self.render_preview_html(self.markdown_editor.toPlainText()))

    def render_preview_html(self, text: str):
        lines = text.splitlines()
        title = self.song_title_input.text().strip() or self.current_song_title or "Untitled Song"
        key = self.song_key_input.text().strip()

        body_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip() or title
                continue
            key_match = re.match(r"^\*\*Key:\*\*\s*(.*)$", stripped, re.IGNORECASE)
            if key_match:
                key = key_match.group(1).strip() or key
                continue
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                body_lines.append(line)

        if not body_lines:
            body_lines = [line for line in lines if line.strip() and not line.strip().startswith("# ")]

        key = key or "C"

        chart_text = "\n".join(body_lines).strip("\n")
        body = f"<pre class='chart-pre'>{escape(chart_text)}</pre>" if chart_text else "<pre class='chart-pre'></pre>"
        return f"""
<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<style>
    body {{
        margin: 0;
        padding: 24px;
        background: #1f1f1f;
        color: #f3f3f3;
        font-family: 'Avenir Next', 'Segoe UI', sans-serif;
    }}
    .sheet {{
        max-width: 980px;
    }}
    .header {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 8px;
    }}
    .title {{
        font-size: 44px;
        line-height: 1;
        font-weight: 800;
        letter-spacing: 0.02em;
    }}
    .key {{
        margin-top: 6px;
        margin-bottom: 18px;
        font-size: 22px;
        font-weight: 700;
        color: #e7e7e7;
    }}
    .section {{
        margin-top: 18px;
        margin-bottom: 6px;
    }}
    .chart-pre {{
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
        color: #f5f5f5;
        font-family: Menlo, Monaco, 'Courier New', monospace;
        font-size: 38px;
        line-height: 1.10;
        white-space: pre;
    }}
</style>
</head>
<body>
    <div class='sheet'>
        <div class='header'>
            <div class='title'>{escape(title)}</div>
        </div>
        <div class='key'>Key: {escape(key)}</div>
        {body}
    </div>
</body>
</html>
"""

    def open_associated_url(self, url_text: str):
        if not url_text:
            return
        url = QUrl(url_text)
        if not url.isValid() or not url.scheme():
            QMessageBox.information(self, "Invalid URL", "Please enter a full URL including https://")
            return
        QDesktopServices.openUrl(url)

    def load_project_file(self, path: Path):
        self._loading_project = True
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._loading_project = False
            QMessageBox.warning(self, "Load error", f"Could not load chart: {exc}")
            return

        title = str(data.get("title", "") or self.current_song_title or "Untitled Song")
        song_key = str(data.get("song_key", "") or "").strip()
        remote_url = str(data.get("remote_url", "") or "")
        if not remote_url:
            remote_url = str(data.get("youtube_url", "") or data.get("spotify_url", "") or "")
        chart_text = str(data.get("chart_text", "") or "")
        if not song_key and chart_text:
            key_match = re.search(r"^\*\*Key:\*\*\s*(.+)$", chart_text, flags=re.IGNORECASE | re.MULTILINE)
            if key_match:
                song_key = key_match.group(1).strip()

        self.song_title_input.setText(title)
        self.song_key_input.setText(song_key)
        self.remote_url_input.setText(remote_url)

        self.markdown_editor.blockSignals(True)
        if chart_text.strip():
            self.markdown_editor.setPlainText(chart_text)
        else:
            self.markdown_editor.setPlainText(self.default_chart_template(title, song_key))
        self.markdown_editor.blockSignals(False)

        self.normalize_chart_spacing()
        self.update_preview()

        if self.current_library_entry:
            self.current_library_entry["title"] = title
            self.current_library_entry["song_key"] = song_key
            self.current_library_entry["remote_url"] = remote_url
            self.current_library_entry["project_path"] = str(path)
            self.remember_song(dict(self.current_library_entry))

        self._loading_project = False

    def schedule_project_save(self):
        if self._loading_project or not self.project_path:
            return
        self.project_save_timer.start(250)

    def project_data(self):
        return {
            "version": 4,
            "working_directory": str(self.working_dir),
            "project_path": str(self.project_path) if self.project_path else "",
            "title": self.song_title_input.text().strip() or self.current_song_title or "Untitled Song",
            "song_key": self.song_key_input.text().strip(),
            "remote_url": self.remote_url_input.text().strip(),
            "playlist": str(self.current_library_entry.get("playlist", "")) if self.current_library_entry else "",
            "chart_text": self.markdown_editor.toPlainText(),
            "library_entry": dict(self.current_library_entry) if self.current_library_entry else {},
        }

    def autosave_project(self):
        if not self.project_path:
            return
        try:
            self.project_path.parent.mkdir(parents=True, exist_ok=True)
            self.project_path.write_text(json.dumps(self.project_data(), indent=2), encoding="utf-8")
        except Exception as exc:
            self.statusBar().showMessage(f"Autosave failed: {exc}")

    def save_project_as(self):
        if not self.current_library_entry:
            QMessageBox.information(self, "No song selected", "Select or add a song before saving a project.")
            return

        default_stem = self.slugify(self.song_title_input.text().strip() or self.current_song_title or "song")
        default_path = self.working_dir / f"{default_stem}.mccp.json"
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(default_path),
            "MCCP Project (*.mccp.json);;JSON (*.json)",
        )
        if not selected_path:
            return

        target = Path(selected_path)
        if target.suffix.lower() not in {".json", ".mccp.json"}:
            target = target.with_suffix(".mccp.json")

        self.project_path = target
        self.current_library_entry["project_path"] = str(self.project_path)
        self.current_library_entry["title"] = self.song_title_input.text().strip() or self.current_song_title or "Untitled Song"
        self.current_library_entry["song_key"] = self.song_key_input.text().strip()
        self.current_library_entry["remote_url"] = self.remote_url_input.text().strip()
        self.remember_song(dict(self.current_library_entry))
        self.autosave_project()
        self.statusBar().showMessage(f"Saved project: {self.project_path}")

    def chart_text_content(self):
        text = self.markdown_editor.toPlainText().strip()
        if text:
            return text + "\n"
        return self.default_chart_template(
            self.song_title_input.text().strip() or "Untitled Song",
            self.song_key_input.text().strip(),
        )

    def export_rendered_chart(self):
        if not self.current_library_entry:
            QMessageBox.information(self, "No song selected", "Select or add a song before exporting.")
            return

        default_stem = self.slugify(self.song_title_input.text().strip() or self.current_song_title or "song")
        default_path = self.working_dir / f"{default_stem}_rendered.html"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Rendered Chart",
            str(default_path),
            "HTML (*.html)",
        )
        if not path:
            return

        target = Path(path)
        if target.suffix.lower() != ".html":
            target = target.with_suffix(".html")

        try:
            html = self.render_preview_html(self.markdown_editor.toPlainText())
            target.write_text(html, encoding="utf-8")
            self.statusBar().showMessage(f"Exported rendered chart: {target}")
        except Exception as exc:
            QMessageBox.warning(self, "Export error", f"Could not export rendered chart: {exc}")

    def export_markdown(self):
        if not self.current_library_entry:
            QMessageBox.information(self, "No song selected", "Select or add a song before exporting.")
            return

        default_stem = self.slugify(self.song_title_input.text().strip() or self.current_song_title or "song")
        default_path = self.working_dir / f"{default_stem}.md"
        path, _ = QFileDialog.getSaveFileName(self, "Export chart", str(default_path), "Markdown (*.md)")
        if not path:
            return

        try:
            target = Path(path)
            if target.suffix.lower() != ".md":
                target = target.with_suffix(".md")
            target.write_text(self.chart_text_content(), encoding="utf-8")
            self.statusBar().showMessage(f"Exported {target}")
        except Exception as exc:
            QMessageBox.warning(self, "Export error", f"Could not export markdown: {exc}")

    def closeEvent(self, event):
        self.autosave_project()
        self.save_song_library()
        super().closeEvent(event)
