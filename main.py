import sys, json, math
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QDoubleSpinBox, QLineEdit, QListWidget,
    QListWidgetItem, QSplitter, QTableWidget, QTableWidgetItem, QMessageBox,
    QComboBox, QSpinBox, QAbstractItemView
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


APP_TITLE = "NNS Transcriber"


class Waveform(QWidget):
    markerClicked = Signal(float)
    loopChanged = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(180)
        self.duration = 1.0
        self.position = 0.0
        self.loop_start = 0.0
        self.loop_end = 1.0
        self.dragging_loop = None
        self.markers = []  # (seconds, label)
        self.setMouseTracking(True)

    def set_duration(self, seconds):
        self.duration = max(0.001, float(seconds))
        self.loop_end = min(self.loop_end, self.duration)
        self.update()

    def set_position(self, seconds):
        self.position = max(0, min(float(seconds), self.duration))
        self.update()

    def x_to_time(self, x):
        return max(0, min(self.duration, x / max(1, self.width()) * self.duration))

    def time_to_x(self, t):
        return int(t / self.duration * self.width())

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#17191d"))

        # Simple deterministic pseudo-waveform. Replace with decoded peaks later.
        pen = QPen(QColor("#7c8798"))
        pen.setWidth(1)
        p.setPen(pen)
        mid = self.height() // 2
        last = mid
        samples = max(100, self.width())
        for i in range(samples):
            x = int(i / samples * self.width())
            envelope = 0.15 + 0.85 * abs(math.sin(i * 0.047) * math.sin(i * 0.013))
            y = int(mid - envelope * (self.height() * 0.34) * math.sin(i * 0.21))
            p.drawLine(x, mid - (mid-y)//2, x, mid + (y-mid)//2)
            last = y

        # Loop region
        x1 = self.time_to_x(self.loop_start)
        x2 = self.time_to_x(self.loop_end)
        p.fillRect(x1, 0, max(1, x2-x1), self.height(), QColor(76, 120, 170, 45))
        p.setPen(QPen(QColor("#65a8ff"), 2))
        p.drawLine(x1, 0, x1, self.height())
        p.drawLine(x2, 0, x2, self.height())

        # Markers
        for t, label in self.markers:
            x = self.time_to_x(t)
            p.setPen(QPen(QColor("#e7b35c"), 2))
            p.drawLine(x, 0, x, self.height())
            p.setPen(QColor("#e7b35c"))
            p.drawText(x + 4, 18, label[:24])

        # Playhead
        x = self.time_to_x(self.position)
        p.setPen(QPen(QColor("#ff5f57"), 2))
        p.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, e):
        t = self.x_to_time(e.position().x())
        if e.button() == Qt.LeftButton:
            if abs(t - self.loop_start) < self.duration * 0.02:
                self.dragging_loop = "start"
            elif abs(t - self.loop_end) < self.duration * 0.02:
                self.dragging_loop = "end"
            else:
                self.markerClicked.emit(t)

    def mouseMoveEvent(self, e):
        if not self.dragging_loop:
            return
        t = self.x_to_time(e.position().x())
        if self.dragging_loop == "start":
            self.loop_start = min(t, self.loop_end - 0.05)
        else:
            self.loop_end = max(t, self.loop_start + 0.05)
        self.loopChanged.emit(self.loop_start, self.loop_end)
        self.update()

    def mouseReleaseEvent(self, e):
        self.dragging_loop = None


class ChartTable(QTableWidget):
    changed = Signal()

    def __init__(self):
        super().__init__(0, 7)
        self.setHorizontalHeaderLabels(
            ["Bar", "Beat", "Number", "Quality", "Rhythm / Hits", "Audio Start", "Audio End"]
        )
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.cellChanged.connect(lambda *_: self.changed.emit())

    def add_row(self, bar=1, beat=1, number="1", quality="", rhythm="", start="", end=""):
        r = self.rowCount()
        self.insertRow(r)
        vals = [bar, beat, number, quality, rhythm, start, end]
        for c, v in enumerate(vals):
            self.setItem(r, c, QTableWidgetItem(str(v)))
        self.changed.emit()

    def rows(self):
        out = []
        for r in range(self.rowCount()):
            out.append({
                "bar": self.item(r,0).text() if self.item(r,0) else "",
                "beat": self.item(r,1).text() if self.item(r,1) else "",
                "number": self.item(r,2).text() if self.item(r,2) else "",
                "quality": self.item(r,3).text() if self.item(r,3) else "",
                "rhythm": self.item(r,4).text() if self.item(r,4) else "",
                "start": self.item(r,5).text() if self.item(r,5) else "",
                "end": self.item(r,6).text() if self.item(r,6) else "",
            })
        return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1300, 800)

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.9)

        self.song_path = None
        self.project_path = None
        self.loop_enabled = True
        self.loop_start = 0.0
        self.loop_end = 1.0
        self.markers = []

        self.wave = Waveform()
        self.wave.markerClicked.connect(self.seek)
        self.wave.loopChanged.connect(self.set_loop)

        # Controls
        self.load_btn = QPushButton("Load Song")
        self.play_btn = QPushButton("▶ Play")
        self.loop_btn = QPushButton("↻ Loop")
        self.mark_btn = QPushButton("＋ Marker")
        self.export_btn = QPushButton("Export Markdown")
        self.save_btn = QPushButton("Save Project")
        self.open_project_btn = QPushButton("Open Project")

        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.25, 1.5)
        self.speed.setSingleStep(0.05)
        self.speed.setValue(1.0)
        self.speed.setSuffix("×")

        self.pos_slider = QSlider(Qt.Horizontal)
        self.time_label = QLabel("0:00.000 / 0:00.000")

        controls = QHBoxLayout()
        for w in [self.load_btn, self.play_btn, self.loop_btn, self.mark_btn]:
            controls.addWidget(w)
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(self.speed)
        controls.addStretch()
        controls.addWidget(self.time_label)

        # Marker list
        self.marker_list = QListWidget()
        self.marker_input = QLineEdit()
        self.marker_input.setPlaceholderText("Marker label, e.g. 'Verse / bass enters'")
        add_marker_btn = QPushButton("Add marker at playhead")
        add_marker_btn.clicked.connect(self.add_marker)
        marker_box = QVBoxLayout()
        marker_box.addWidget(QLabel("Markers"))
        marker_box.addWidget(self.marker_list)
        marker_box.addWidget(self.marker_input)
        marker_box.addWidget(add_marker_btn)
        marker_widget = QWidget()
        marker_widget.setLayout(marker_box)

        # NNS chart
        self.section = QLineEdit("VERSE")
        self.section.setPlaceholderText("Section name")
        self.chart = ChartTable()
        self.add_bar_btn = QPushButton("Add chart row")
        self.delete_bar_btn = QPushButton("Delete selected row")
        chart_controls = QHBoxLayout()
        chart_controls.addWidget(QLabel("Section"))
        chart_controls.addWidget(self.section)
        chart_controls.addStretch()
        chart_controls.addWidget(self.add_bar_btn)
        chart_controls.addWidget(self.delete_bar_btn)

        chart_box = QVBoxLayout()
        chart_box.addLayout(chart_controls)
        chart_box.addWidget(self.chart)
        chart_widget = QWidget()
        chart_widget.setLayout(chart_box)

        right = QSplitter(Qt.Vertical)
        right.addWidget(marker_widget)
        right.addWidget(chart_widget)
        right.setSizes([250, 500])

        main = QWidget()
        layout = QVBoxLayout(main)
        layout.addLayout(controls)
        layout.addWidget(self.wave)
        layout.addWidget(self.pos_slider)
        layout.addWidget(right)
        self.setCentralWidget(main)

        self.load_btn.clicked.connect(self.load_song)
        self.play_btn.clicked.connect(self.toggle_play)
        self.loop_btn.clicked.connect(self.toggle_loop)
        self.mark_btn.clicked.connect(self.add_marker)
        self.export_btn.clicked.connect(self.export_markdown)
        self.save_btn.clicked.connect(self.save_project)
        self.open_project_btn.clicked.connect(self.open_project)
        self.add_bar_btn.clicked.connect(lambda: self.chart.add_row())
        self.delete_bar_btn.clicked.connect(self.delete_selected)
        self.pos_slider.sliderMoved.connect(self.seek_slider)
        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(self.on_duration)

        # Menus
        file_menu = self.menuBar().addMenu("&File")
        for button, shortcut in [
            (self.load_btn, "Ctrl+O"),
            (self.open_project_btn, "Ctrl+Shift+O"),
            (self.save_btn, "Ctrl+S"),
            (self.export_btn, "Ctrl+E"),
        ]:
            action = QAction(button.text(), self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(button.click)
            file_menu.addAction(action)

        # Keyboard shortcuts
        self.play_action = QAction(self)
        self.play_action.setShortcut(QKeySequence("Space"))
        self.play_action.triggered.connect(self.toggle_play)
        self.addAction(self.play_action)

        self.mark_action = QAction(self)
        self.mark_action.setShortcut(QKeySequence("M"))
        self.mark_action.triggered.connect(self.add_marker)
        self.addAction(self.mark_action)

        self.loop_action = QAction(self)
        self.loop_action.setShortcut(QKeySequence("L"))
        self.loop_action.triggered.connect(self.toggle_loop)
        self.addAction(self.loop_action)

        self.seek_timer = QTimer(self)
        self.seek_timer.timeout.connect(self.enforce_loop)
        self.seek_timer.start(50)

        self.statusBar().showMessage(
            "Space Play/Pause   L Loop   M Marker   ←/→ seek   Drag loop edges on waveform"
        )

        self._updating_slider = False

    def load_song(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose audio", "", "Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg)"
        )
        if not path:
            return
        self.song_path = Path(path)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.setWindowTitle(f"{APP_TITLE} — {self.song_path.name}")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶ Play")
        else:
            self.player.play()
            self.play_btn.setText("❚❚ Pause")

    def toggle_loop(self):
        self.loop_enabled = not self.loop_enabled
        self.loop_btn.setText("↻ Loop" if self.loop_enabled else "Loop Off")

    def set_loop(self, start, end):
        self.loop_start, self.loop_end = start, end
        self.wave.loop_start, self.wave.loop_end = start, end

    def enforce_loop(self):
        if not self.loop_enabled or self.player.duration() <= 0:
            return
        if self.player.position() >= int(self.loop_end * 1000):
            self.player.setPosition(int(self.loop_start * 1000))
            if self.player.playbackState() != QMediaPlayer.PlayingState:
                self.player.play()

    def on_duration(self, ms):
        sec = max(0.001, ms / 1000)
        self.wave.set_duration(sec)
        self.loop_end = sec
        self.wave.loop_end = sec
        self.pos_slider.setRange(0, max(1, ms))
        self.update_time_label(ms)

    def on_position(self, ms):
        sec = ms / 1000
        self.wave.set_position(sec)
        self._updating_slider = True
        self.pos_slider.setValue(ms)
        self._updating_slider = False
        self.update_time_label(ms)

    def update_time_label(self, ms):
        def fmt(x):
            s = x / 1000
            return f"{int(s//60)}:{s%60:06.3f}"
        self.time_label.setText(f"{fmt(ms)} / {fmt(self.player.duration())}")

    def seek(self, sec):
        self.player.setPosition(int(sec * 1000))

    def seek_slider(self, ms):
        self.player.setPosition(ms)

    def add_marker(self):
        t = self.player.position() / 1000
        label = self.marker_input.text().strip() or f"Marker {len(self.markers)+1}"
        self.markers.append({"time": t, "label": label})
        self.marker_list.addItem(f"{self.fmt(t)}  —  {label}")
        self.wave.markers = [(m["time"], m["label"]) for m in self.markers]
        self.wave.update()
        self.marker_input.clear()

    def fmt(self, s):
        return f"{int(s//60)}:{s%60:06.3f}"

    def delete_selected(self):
        rows = sorted({i.row() for i in self.chart.selectedIndexes()}, reverse=True)
        for r in rows:
            self.chart.removeRow(r)

    def save_project(self):
        if not self.song_path:
            QMessageBox.information(self, "No song", "Load a song before saving a project.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", "", "NNS Project (*.nns.json)"
        )
        if not path:
            return
        data = self.project_data()
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.project_path = Path(path)
        self.statusBar().showMessage(f"Saved {path}")

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "NNS Project (*.nns.json)"
        )
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        audio_path = data.get("audio_path")
        if audio_path and Path(audio_path).exists():
            self.song_path = Path(audio_path)
            self.player.setSource(QUrl.fromLocalFile(audio_path))
        self.loop_start = float(data.get("loop_start", 0))
        self.loop_end = float(data.get("loop_end", 1))
        self.loop_enabled = bool(data.get("loop_enabled", True))
        self.wave.loop_start = self.loop_start
        self.wave.loop_end = self.loop_end

        self.markers = data.get("markers", [])
        self.marker_list.clear()
        for m in self.markers:
            self.marker_list.addItem(f"{self.fmt(m['time'])}  —  {m['label']}")
        self.wave.markers = [(m["time"], m["label"]) for m in self.markers]

        self.chart.setRowCount(0)
        for row in data.get("chart", []):
            self.chart.add_row(
                row.get("bar",""), row.get("beat",""), row.get("number","1"),
                row.get("quality",""), row.get("rhythm",""),
                row.get("start",""), row.get("end","")
            )
        self.section.setText(data.get("section", "VERSE"))
        self.project_path = Path(path)
        self.wave.update()
        self.statusBar().showMessage(f"Opened {path}")

    def project_data(self):
        return {
            "version": 1,
            "audio_path": str(self.song_path) if self.song_path else "",
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
            "loop_enabled": self.loop_enabled,
            "markers": self.markers,
            "section": self.section.text(),
            "chart": self.chart.rows(),
        }

    def export_markdown(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Nashville chart", "", "Markdown (*.md)"
        )
        if not path:
            return

        rows = self.chart.rows()
        section = self.section.text().strip() or "UNTITLED"
        lines = [
            f"# {self.song_path.stem if self.song_path else 'Untitled Song'}",
            "",
            f"## {section}",
            "",
        ]

        # Export compact bar rows.
        bars = {}
        for r in rows:
            bars.setdefault(str(r["bar"]), []).append(r)

        if bars:
            lines.append("| " + " | ".join(f"Bar {b}" for b in bars) + " |")
            lines.append("| " + " | ".join("---" for _ in bars) + " |")
            cells = []
            for b in bars:
                vals = []
                for r in bars[b]:
                    n = r["number"] or "—"
                    q = r["quality"]
                    rh = f" ({r['rhythm']})" if r["rhythm"] else ""
                    vals.append(f"{n}{q}{rh}")
                cells.append("<br>".join(vals))
            lines.append("| " + " | ".join(cells) + " |")
            lines.append("")

        lines += ["## Markers", ""]
        for m in self.markers:
            lines.append(f"- `{self.fmt(m['time'])}` — {m['label']}")

        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.statusBar().showMessage(f"Exported {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
