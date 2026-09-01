from __future__ import annotations

import os
import sys
import json
from collections import Counter
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QSettings, QSize, Qt, QThreadPool, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QProgressBar, QPushButton, QSizePolicy, QStyle, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core import (
    APP_NAME, APP_VERSION, DEFAULT_RULES, PlannedMove, ScanResult, execute_plan, is_admin,
    load_history, restart_as_admin, scan_folder, undo_last,
)


THEMES = {
    "Light": {
        "bg": "#f6f7f4", "sidebar": "#ffffff", "card": "#ffffff", "soft": "#f1f3ef",
        "text": "#1c211e", "muted": "#6f7872", "border": "#e2e6e1", "accent": "#17382c",
        "accentText": "#ffffff", "highlight": "#dfeee6", "danger": "#a64638",
    },
    "Dark": {
        "bg": "#0f1210", "sidebar": "#141815", "card": "#181d1a", "soft": "#202722",
        "text": "#f2f5f3", "muted": "#9ba69f", "border": "#2b342e", "accent": "#a9d3bc",
        "accentText": "#102219", "highlight": "#243c30", "danger": "#ff8b7a",
    },
    "Contrast": {
        "bg": "#000000", "sidebar": "#050505", "card": "#080808", "soft": "#111111",
        "text": "#ffffff", "muted": "#e2e2e2", "border": "#b6ff00", "accent": "#b6ff00",
        "accentText": "#000000", "highlight": "#1f3100", "danger": "#ff7272",
    },
}


def asset_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath("assets", *parts)

FONT_OPTIONS = {
    "System clean": "Segoe UI",
    "Inter (Aptos-style)": "Inter",
    "Bahnschrift": "Bahnschrift",
    "Orbitron": "Orbitron",
    "Cascadia Mono": "Cascadia Mono",
}


def stylesheet(theme: dict[str, str], font_family: str) -> str:
    contrast = theme is THEMES["Contrast"]
    contrast_rules = """
    QFrame#sidebar { border-right: 2px solid #b6ff00; }
    QFrame#topbar { border-bottom: 2px solid #b6ff00; }
    QFrame#hero, QFrame[class=\"card\"] { border: 2px solid #b6ff00; border-radius: 4px; }
    QPushButton#secondary, QComboBox, QCheckBox { border: 2px solid #b6ff00; border-radius: 3px; }
    QTableWidget { border: 2px solid #b6ff00; }
    QHeaderView::section { border-bottom: 2px solid #b6ff00; }
    QLabel#badge { border: 2px solid #b6ff00; border-radius: 3px; }
    """ if contrast else ""
    return f"""
    * {{ font-family: '{font_family}'; font-size: 13px; color: {theme['text']}; }}
    QMainWindow, QDialog, QWidget#root {{ background: {theme['bg']}; }}
    QFrame#sidebar {{ background: {theme['sidebar']}; border-right: 1px solid {theme['border']}; }}
    QFrame#topbar {{ background: {theme['bg']}; border-bottom: 1px solid {theme['border']}; }}
    QFrame#hero {{ background: {theme['highlight']}; border: 1px solid {theme['border']}; border-radius: 18px; }}
    QFrame[class="card"] {{ background: {theme['card']}; border: 1px solid {theme['border']}; border-radius: 14px; }}
    QLabel#brand {{ font-size: 19px; font-weight: 700; }}
    QLabel#eyebrow {{ color: {theme['muted']}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
    QLabel#heroTitle {{ color: {theme['text']}; font-size: 30px; font-weight: 700; }}
    QLabel#heroCopy, QLabel[class="muted"] {{ color: {theme['muted']}; }}
    QLabel#badge {{ background: {theme['card']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 600; }}
    QPushButton {{ background: transparent; border: 0; border-radius: 9px; padding: 10px 14px; text-align: left; }}
    QPushButton:hover {{ background: {theme['soft']}; }}
    QPushButton#primary {{ background: {theme['accent']}; color: {theme['accentText']}; font-weight: 700; text-align: center; padding: 11px 18px; }}
    QPushButton#primary:hover {{ background: {theme['accent']}; opacity: .9; }}
    QPushButton#secondary {{ background: {theme['card']}; border: 1px solid {theme['border']}; font-weight: 600; text-align: center; }}
    QPushButton#navActive {{ background: {theme['highlight']}; color: {theme['text']}; font-weight: 700; }}
    QPushButton:disabled {{ color: {theme['muted']}; background: {theme['soft']}; }}
    QComboBox, QCheckBox {{ background: {theme['card']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 7px 9px; }}
    QLineEdit {{ background: {theme['card']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 9px 10px; selection-background-color: {theme['accent']}; }}
    QLineEdit:focus {{ border: 2px solid {theme['accent']}; }}
    QCheckBox {{ padding: 8px 9px; spacing: 9px; }}
    QCheckBox::indicator {{ width: 14px; height: 14px; border: 2px solid {theme['border']}; border-radius: 2px; background: {theme['card']}; }}
    QCheckBox::indicator:checked {{ background: {theme['accent']}; border: 2px solid {theme['accent']}; image: none; }}
    QCheckBox::indicator:hover {{ border-color: {theme['accent']}; }}
    QComboBox QAbstractItemView {{ background: {theme['card']}; color: {theme['text']}; selection-background-color: {theme['highlight']}; border: 1px solid {theme['border']}; }}
    QTableWidget {{ background: {theme['card']}; alternate-background-color: {theme['soft']}; border: 0; gridline-color: {theme['border']}; selection-background-color: {theme['highlight']}; selection-color: {theme['text']}; }}
    QHeaderView::section {{ background: {theme['soft']}; color: {theme['muted']}; border: 0; border-bottom: 1px solid {theme['border']}; padding: 9px; font-size: 11px; font-weight: 700; }}
    QScrollBar:vertical {{ background: {theme['card']}; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {theme['border']}; border-radius: 5px; min-height: 30px; }}
    QProgressBar {{ background: {theme['soft']}; border: 0; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {theme['accent']}; border-radius: 4px; }}
    {contrast_rules}
    """


def register_bundled_fonts() -> None:
    """Make the app's open fonts available without requiring Windows to install them."""
    for name in ("Inter.ttf", "Orbitron.ttf"):
        QFontDatabase.addApplicationFont(str(asset_path("fonts", name)))


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)


class Worker(QRunnable):
    def __init__(self, function: Callable):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.function(self.signals.progress.emit)
        except Exception as error:
            self.signals.error.emit(str(error))
        else:
            self.signals.finished.emit(result)


class TidyDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, message: str, *, confirm: bool = False, action: str = "Continue"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(asset_path("tidy-logo.svg"))))
        self.setModal(True)
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(15)
        heading = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(QIcon(str(asset_path("tidy-logo.svg"))).pixmap(46, 46))
        heading.addWidget(mark)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        heading.addWidget(title_label)
        heading.addStretch()
        layout.addLayout(heading)
        body = QLabel(message)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setProperty("class", "muted")
        layout.addWidget(body)
        buttons = QDialogButtonBox()
        if confirm:
            cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
            cancel.setObjectName("secondary")
        accept = buttons.addButton(action if confirm else "Done", QDialogButtonBox.ButtonRole.AcceptRole)
        accept.setObjectName("primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def ask_tidy(parent: QWidget, title: str, message: str, action: str = "Continue") -> bool:
    return TidyDialog(parent, title, message, confirm=True, action=action).exec() == QDialog.DialogCode.Accepted


def tell_tidy(parent: QWidget, title: str, message: str) -> None:
    TidyDialog(parent, title, message).exec()


class SmartRulesDialog(QDialog):
    FIELDS = (
        ("work", "Work keywords"),
        ("personal", "Personal keywords"),
        ("video_edits", "Video edit keywords"),
        ("presentations", "Presentation keywords"),
        ("screenshots", "Screenshot keywords"),
    )

    def __init__(self, parent: QWidget, rules: dict):
        super().__init__(parent)
        self.setWindowTitle("Customize smart rules")
        self.setWindowIcon(QIcon(str(asset_path("tidy-logo.svg"))))
        self.setModal(True)
        self.setMinimumWidth(650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 22)
        layout.setSpacing(13)
        title = QLabel("Customize smart rules")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        note = QLabel("Use comma-separated words or phrases. Tidy matches them locally against filenames and, when enabled, document excerpts.")
        note.setWordWrap(True)
        note.setProperty("class", "muted")
        layout.addWidget(note)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.inputs: dict[str, QLineEdit] = {}
        for key, label in self.FIELDS:
            field = QLineEdit(str(rules.get(key, DEFAULT_RULES[key])))
            field.setClearButtonEnabled(True)
            self.inputs[key] = field
            form.addRow(label, field)
        layout.addLayout(form)
        self.group_documents = QCheckBox("Automatically group documents with similar names")
        self.group_documents.setChecked(bool(rules.get("group_documents", True)))
        layout.addWidget(self.group_documents)
        actions = QHBoxLayout()
        reset = QPushButton("Restore defaults")
        reset.setObjectName("secondary")
        reset.clicked.connect(self.restore_defaults)
        actions.addWidget(reset)
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save & rescan")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def restore_defaults(self) -> None:
        for key, _label in self.FIELDS:
            self.inputs[key].setText(str(DEFAULT_RULES[key]))
        self.group_documents.setChecked(True)

    def selected_rules(self) -> dict:
        rules = {key: field.text().strip() for key, field in self.inputs.items()}
        rules["group_documents"] = self.group_documents.isChecked()
        return rules


class TidyWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tidy — Native file organizer")
        self.setWindowIcon(QIcon(str(asset_path("tidy-logo.svg"))))
        self.resize(1220, 790)
        self.setMinimumSize(1000, 650)
        self.settings = QSettings("Tidy", "Tidy")
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(2)
        self.workers: set[Worker] = set()
        self.folder: Path | None = None
        self.plan: list[PlannedMove] = []
        self.busy = False
        self.theme_name = self.settings.value("theme", "Light")
        self.font_name = self.settings.value("font", "System clean")
        try:
            saved_rules = json.loads(str(self.settings.value("smart_rules", "{}")))
        except (TypeError, ValueError, json.JSONDecodeError):
            saved_rules = {}
        self.rules = {**DEFAULT_RULES, **saved_rules}
        if self.font_name == "Aptos":
            self.font_name = "Inter (Aptos-style)"
        self._build_ui()
        self.apply_theme(self.theme_name)
        self._refresh_history()

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(226)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 22, 16, 18)
        side.setSpacing(6)
        brand_row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(asset_path("tidy-logo.svg"))).pixmap(36, 36))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(36, 36)
        logo.setObjectName("badge")
        brand = QLabel("Tidy", objectName="brand")
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        side.addLayout(brand_row)
        side.addSpacing(22)
        self.nav_buttons: list[QPushButton] = []
        nav_items = (
            (QStyle.StandardPixmap.SP_ComputerIcon, "Dashboard", self.show_dashboard),
            (QStyle.StandardPixmap.SP_FileDialogDetailedView, "Move preview", self.show_move_preview),
            (QStyle.StandardPixmap.SP_FileDialogContentsView, "Smart rules", self.show_smart_rules),
            (QStyle.StandardPixmap.SP_BrowserReload, "Activity", self.show_activity),
        )
        for index, (icon, label, action) in enumerate(nav_items):
            button = QPushButton(label)
            button.setIcon(self.style().standardIcon(icon))
            button.setIconSize(QSize(18, 18))
            if index == 0:
                button.setObjectName("navActive")
            button.clicked.connect(lambda _checked=False, target=index, callback=action: self._navigate(target, callback))
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addSpacing(22)
        side.addWidget(QLabel("RESOURCE & ACCESS", objectName="eyebrow"))
        self.admin_chip = QLabel("● Administrator" if is_admin() else "● Standard access")
        self.admin_chip.setProperty("class", "muted")
        side.addWidget(self.admin_chip)
        resource_note = QLabel("One scan thread • no background watcher")
        resource_note.setProperty("class", "muted")
        resource_note.setWordWrap(True)
        side.addWidget(resource_note)
        if not is_admin():
            elevate = QPushButton("Restart as administrator")
            elevate.setObjectName("secondary")
            elevate.clicked.connect(self.elevate)
            side.addWidget(elevate)
        side.addStretch()
        side.addWidget(QLabel("THEME", objectName="eyebrow"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(THEMES.keys())
        self.theme_box.setCurrentText(self.theme_name)
        self.theme_box.currentTextChanged.connect(self.apply_theme)
        side.addWidget(self.theme_box)
        side.addSpacing(6)
        side.addWidget(QLabel("TYPEFACE", objectName="eyebrow"))
        self.font_box = QComboBox()
        self.font_box.addItems(FONT_OPTIONS.keys())
        self.font_box.setCurrentText(self.font_name)
        self.font_box.currentTextChanged.connect(self.apply_font)
        self.font_box.setToolTip("Inter and Orbitron are bundled with Tidy; system fonts use a clean fallback when unavailable.")
        side.addWidget(self.font_box)
        version = QLabel(f"Version {APP_VERSION}")
        version.setProperty("class", "muted")
        side.addWidget(version)
        shell.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        topbar = QFrame(objectName="topbar")
        topbar.setFixedHeight(76)
        top = QHBoxLayout(topbar)
        top.setContentsMargins(32, 12, 32, 12)
        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        title_column.addWidget(QLabel("PRIVATE • ON DEVICE", objectName="eyebrow"))
        top_title = QLabel("Your lightweight file organizer")
        top_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_column.addWidget(top_title)
        top.addLayout(title_column)
        top.addStretch()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setProperty("class", "muted")
        self.folder_label.setMaximumWidth(330)
        self.folder_label.setToolTip("Choose a folder to scan its loose files.")
        top.addWidget(self.folder_label)
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.setObjectName("secondary")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_selected_folder)
        top.addWidget(self.open_folder_button)
        choose_top = QPushButton("Choose folder")
        choose_top.setObjectName("secondary")
        choose_top.clicked.connect(self.choose_folder)
        top.addWidget(choose_top)
        main_layout.addWidget(topbar)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 26, 30, 28)
        body.setSpacing(18)
        hero = QFrame(objectName="hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 23, 28, 23)
        hero_layout.setSpacing(8)
        badge = QLabel("LOCAL-ONLY CONTENT INSPECTION", objectName="badge")
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        hero_layout.addWidget(badge)
        self.hero_title = QLabel("Turn a cluttered folder into a calm one.", objectName="heroTitle")
        self.hero_title.setWordWrap(True)
        hero_layout.addWidget(self.hero_title)
        self.hero_copy = QLabel("Choose a folder. Tidy previews every move and runs only when you ask.", objectName="heroCopy")
        self.hero_copy.setWordWrap(True)
        hero_layout.addWidget(self.hero_copy)
        hero_actions = QHBoxLayout()
        self.primary = QPushButton("Choose a folder")
        self.primary.setObjectName("primary")
        self.primary.clicked.connect(self.choose_folder)
        self.undo = QPushButton("Undo last tidy-up")
        self.undo.setObjectName("secondary")
        self.undo.clicked.connect(self.undo_last)
        hero_actions.addWidget(self.primary)
        hero_actions.addWidget(self.undo)
        hero_actions.addStretch()
        hero_layout.addLayout(hero_actions)
        body.addWidget(hero)

        lower = QHBoxLayout()
        lower.setSpacing(18)
        self.table_card = QFrame()
        self.table_card.setProperty("class", "card")
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_head = QHBoxLayout()
        table_title = QLabel("Move preview")
        table_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.count_label = QLabel("No folder selected")
        self.count_label.setProperty("class", "muted")
        table_head.addWidget(table_title)
        table_head.addStretch()
        table_head.addWidget(self.count_label)
        table_layout.addLayout(table_head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["FILE", "MOVES TO", "TYPE", "WHY"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.open_selected_file)
        self.table.setToolTip("Double-click a file to open it in its usual Windows app.")
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)
        lower.addWidget(self.table_card, 1)

        self.controls = QFrame()
        self.controls.setProperty("class", "card")
        self.controls.setFixedWidth(288)
        control_layout = QVBoxLayout(self.controls)
        control_layout.setContentsMargins(20, 18, 20, 18)
        control_layout.setSpacing(12)
        control_title = QLabel("Scan controls")
        control_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        control_layout.addWidget(control_title)
        self.deep_inspect = QCheckBox("Inspect document contents")
        self.deep_inspect.setToolTip("Reads at most 96 KB from up to 200 local documents. Nothing is uploaded.")
        self.deep_inspect.stateChanged.connect(lambda _state: self.rescan())
        control_layout.addWidget(self.deep_inspect)
        deep_note = QLabel("Off by default. When enabled, Tidy reads small local excerpts from text, Office, and PDF documents to improve Work/Personal placement.")
        deep_note.setWordWrap(True)
        deep_note.setProperty("class", "muted")
        control_layout.addWidget(deep_note)
        self.include_hidden = QCheckBox("Include hidden user files")
        self.include_hidden.stateChanged.connect(lambda _state: self.rescan())
        control_layout.addWidget(self.include_hidden)
        hidden_note = QLabel("System-attributed files, links, Windows, Program Files, whole drives, and critical binary types are always shielded.")
        hidden_note.setWordWrap(True)
        hidden_note.setProperty("class", "muted")
        control_layout.addWidget(hidden_note)
        control_layout.addSpacing(6)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        control_layout.addWidget(self.progress)
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "muted")
        control_layout.addWidget(self.status_label)
        self.summary_label = QLabel("No scan yet")
        self.summary_label.setWordWrap(True)
        self.summary_label.setProperty("class", "muted")
        control_layout.addWidget(self.summary_label)
        control_layout.addStretch()
        rescan_button = QPushButton("Rescan folder")
        rescan_button.setObjectName("secondary")
        rescan_button.clicked.connect(self.rescan)
        control_layout.addWidget(rescan_button)
        lower.addWidget(self.controls)
        body.addLayout(lower, 1)
        main_layout.addWidget(content, 1)
        shell.addWidget(main, 1)

    def apply_theme(self, name: str) -> None:
        if name not in THEMES:
            name = "Light"
        self.theme_name = name
        self.settings.setValue("theme", name)
        self._apply_appearance()

    def _navigate(self, index: int, action: Callable) -> None:
        for current, button in enumerate(self.nav_buttons):
            button.setObjectName("navActive" if current == index else "")
            button.style().unpolish(button)
            button.style().polish(button)
        action()

    def show_dashboard(self) -> None:
        self.primary.setFocus()
        self.status_label.setText("Dashboard ready")

    def show_move_preview(self) -> None:
        self.table.setFocus()
        if self.plan:
            self.status_label.setText(f"Previewing {len(self.plan)} planned moves • double-click a file to open it")
        else:
            self.status_label.setText("Choose a folder to create a move preview")

    def show_smart_rules(self) -> None:
        self.deep_inspect.setFocus()
        dialog = SmartRulesDialog(self, self.rules)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules = dialog.selected_rules()
            self.settings.setValue("smart_rules", json.dumps(self.rules))
            self.status_label.setText("Smart rules saved")
            if self.folder:
                self.rescan()

    def show_activity(self) -> None:
        folder, moves = load_history()
        if not moves:
            tell_tidy(self, "Activity", "No completed tidy-up is available yet. Your next completed sort will appear here and can be undone.")
            return
        preview = "\n".join(f"• {move.name} → {move.destination_folder}" for move in moves[:25])
        more = f"\n…and {len(moves) - 25} more" if len(moves) > 25 else ""
        tell_tidy(self, "Latest activity", f"Last tidy-up in:\n{folder}\n\n{len(moves)} files moved:\n{preview}{more}")

    def apply_font(self, name: str) -> None:
        if name not in FONT_OPTIONS:
            name = "System clean"
        self.font_name = name
        self.settings.setValue("font", name)
        self._apply_appearance()

    def _apply_appearance(self) -> None:
        family = FONT_OPTIONS.get(self.font_name, "Segoe UI")
        available = set(QFontDatabase.families())
        if family not in available:
            family = "Segoe UI"
        QApplication.instance().setFont(QFont(family, 9))
        QApplication.instance().setStyleSheet(stylesheet(THEMES[self.theme_name], family))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(THEMES[self.theme_name]["bg"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(THEMES[self.theme_name]["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(THEMES[self.theme_name]["card"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(THEMES[self.theme_name]["text"]))
        QApplication.instance().setPalette(palette)

    def elevate(self) -> None:
        if ask_tidy(self, "Restart as administrator", "Windows will ask for administrator permission. Continue?", "Restart"):
            if restart_as_admin():
                QApplication.quit()
            else:
                tell_tidy(self, "Could not elevate", "Windows did not start the elevated copy.")

    def choose_folder(self) -> None:
        initial = str(Path.home() / "Downloads" if (Path.home() / "Downloads").exists() else Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Choose a folder for Tidy", initial)
        if selected:
            self.folder = Path(selected)
            self.folder_label.setText(str(self.folder))
            self.folder_label.setToolTip(str(self.folder))
            self.open_folder_button.setEnabled(True)
            self.rescan()

    def open_selected_folder(self) -> None:
        if self.folder and self.folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    def open_selected_file(self, row: int, _column: int) -> None:
        if 0 <= row < len(self.plan):
            source = Path(self.plan[row].source)
            if source.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(source)))

    def rescan(self) -> None:
        if not self.folder or self.busy:
            return
        inspect = self.deep_inspect.isChecked()
        hidden = self.include_hidden.isChecked()
        self._start_worker(
            "Inspecting local files…" if inspect else "Scanning filenames and types…",
            lambda progress: scan_folder(self.folder, hidden, inspect, progress, self.rules),
            self._scan_finished,
        )

    def _scan_finished(self, result: ScanResult) -> None:
        self.plan = result.moves
        preview = self.plan[:500]
        self.table.setRowCount(len(preview))
        for row, move in enumerate(preview):
            values = (move.name, move.destination_folder, move.category, move.reason)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        hidden_rows = len(self.plan) - len(preview)
        self.count_label.setText(f"{len(self.plan)} files" + (f" • first 500 shown" if hidden_rows else ""))
        self.summary_label.setText(f"{result.inspected} locally inspected • {result.skipped_protected} protected skipped")
        if self.plan:
            self.hero_title.setText(f'“{self.folder.name}” is ready for a tidy-up.')
            self.hero_copy.setText(f"Tidy planned {len(self.plan)} safe top-level moves. Review the destination and reason columns before sorting.")
            self.primary.setText(f"Review & sort {len(self.plan)} files")
            self._set_primary_action(f"Review & sort {len(self.plan)} files", self.sort_files)
        else:
            self.hero_title.setText(f'“{self.folder.name}” is already tidy.')
            self.hero_copy.setText("No eligible loose files were found. Protected system files were left untouched.")
            self._set_primary_action("Choose another folder", self.choose_folder)
        self._refresh_history()

    def sort_files(self) -> None:
        if not self.folder or not self.plan or self.busy:
            return
        categories = Counter(move.category for move in self.plan)
        summary = "\n".join(f"  • {count} {category}" for category, count in categories.most_common())
        message = f"Tidy will move {len(self.plan)} files inside:\n{self.folder}\n\n{summary}\n\nExisting files will never be overwritten. Continue?"
        if not ask_tidy(self, "Approve this tidy-up", message, "Sort files"):
            return
        plan = list(self.plan)
        folder = self.folder
        self._start_worker("Moving files…", lambda progress: execute_plan(folder, plan, progress), self._sort_finished)

    def _sort_finished(self, completed: list[PlannedMove]) -> None:
        self.plan = []
        self.table.setRowCount(0)
        self.count_label.setText("No moves planned")
        self.hero_title.setText(f'“{self.folder.name}” is looking beautifully tidy.')
        self.hero_copy.setText(f"{len(completed)} files found their proper place. Undo remains available after restarting Tidy.")
        self._set_primary_action("Choose another folder", self.choose_folder)
        self._refresh_history()
        tell_tidy(self, "Tidy-up complete", f"Organized {len(completed)} files. Nothing was deleted or overwritten.")

    def undo_last(self) -> None:
        _, history = load_history()
        if not history:
            tell_tidy(self, "Nothing to undo", "No previous Tidy move is available.")
            return
        if not ask_tidy(self, "Undo last tidy-up", f"Restore {len(history)} files to their original folder?", "Restore files"):
            return
        self._start_worker("Restoring files…", lambda progress: undo_last(progress), self._undo_finished)

    def _undo_finished(self, result: tuple[int, Path | None]) -> None:
        restored, folder = result
        self._refresh_history()
        if folder and folder.exists():
            self.folder = folder
            self.rescan()
        tell_tidy(self, "Tidy-up undone", f"Restored {restored} files.")

    def _refresh_history(self) -> None:
        _, moves = load_history()
        self.undo.setEnabled(bool(moves) and not self.busy)

    def _set_primary_action(self, label: str, action: Callable) -> None:
        self.primary.setText(label)
        try:
            self.primary.clicked.disconnect()
        except RuntimeError:
            pass
        self.primary.clicked.connect(action)

    def _start_worker(self, label: str, function: Callable, finished: Callable) -> None:
        if self.busy:
            return
        self.busy = True
        self.status_label.setText(label)
        self.progress.setValue(2)
        self.primary.setEnabled(False)
        self.undo.setEnabled(False)
        worker = Worker(function)
        self.workers.add(worker)
        worker.signals.progress.connect(self._update_progress)
        worker.signals.error.connect(lambda message, active=worker: self._worker_error(message, active))
        worker.signals.finished.connect(lambda result, active=worker: self._worker_finished(result, finished, active))
        self.pool.start(worker)

    def _update_progress(self, completed: int, total: int, name: str) -> None:
        self.progress.setValue(round(completed / max(1, total) * 100))
        self.status_label.setText(f"{completed}/{total} • {name}")

    def _worker_finished(self, result, callback: Callable, worker: Worker) -> None:
        self.workers.discard(worker)
        self.busy = False
        self.progress.setValue(100)
        self.status_label.setText("Ready")
        self.primary.setEnabled(True)
        try:
            callback(result)
        except Exception as error:
            self._worker_error(f"The scan completed, but its preview could not be displayed:\n{error}")

    def _worker_error(self, message: str, worker: Worker | None = None) -> None:
        if worker is not None:
            self.workers.discard(worker)
        self.busy = False
        self.progress.setValue(0)
        self.status_label.setText("Needs attention")
        self.primary.setEnabled(True)
        self._refresh_history()
        tell_tidy(self, "Tidy could not continue", message)


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv
    resource_test = "--resource-test" in sys.argv
    if smoke_test or resource_test:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(QIcon(str(asset_path("tidy-logo.svg"))))
    app.setStyle("Fusion")
    register_bundled_fonts()
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = TidyWindow()
    if smoke_test:
        print("Tidy smoke test OK")
        return 0
    window.show()
    if resource_test:
        QTimer.singleShot(5000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
