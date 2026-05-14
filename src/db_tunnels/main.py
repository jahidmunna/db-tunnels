"""
DB Tunnels — macOS GUI
Launch: uv run db-tunnels  or  uv run python -m db_tunnels.main
"""

import os
import sys
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QTextEdit,
    QSplitter, QFrame, QDialog, QDialogButtonBox, QLineEdit,
    QSpinBox, QFormLayout, QScrollArea, QGroupBox, QCheckBox,
    QMessageBox, QToolButton, QPlainTextEdit,
    QTabWidget, QGridLayout,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

from .tunnel_model import Tunnel, ForwardRule, load_tunnels, save_tunnels
from .tunnel_manager import TunnelManager, TunnelStatus
from .preflight import CheckResult, Severity, run_all_checks, run_auto_fix
from .ssh_key_manager import (
    SSHKey, discover_keys, generate_key, copy_key_to_server,
    default_key_path, KEY_TYPES, SSH_DIR,
)


# ── Palette ─────────────────────────────────────────────────────────────────

BG       = "#0f0f14"
SIDEBAR  = "#16161e"
CARD     = "#1e1e2a"
CARD_HOV = "#252535"
BORDER   = "#2a2a3a"
ACCENT   = "#7c6af7"
ACCENT2  = "#56cfb2"
RED      = "#f04b4b"
ORANGE   = "#f7965a"
GREEN    = "#56cfb2"
TEXT     = "#e0e0f0"
TEXT_DIM = "#7a7a9a"
TEXT_SUB = "#4a4a6a"

STATUS_COLORS = {
    TunnelStatus.STOPPED:   ("#3a3a4a", TEXT_DIM),
    TunnelStatus.STARTING:  ("#3a2e00", ORANGE),
    TunnelStatus.CONNECTED: ("#0d2b22", GREEN),
    TunnelStatus.ERROR:     ("#2b0d0d", RED),
}

STATUS_LABELS = {
    TunnelStatus.STOPPED:   "● Stopped",
    TunnelStatus.STARTING:  "◎ Starting",
    TunnelStatus.CONNECTED: "● Connected",
    TunnelStatus.ERROR:     "● Error",
}

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background-color: {BG};
}}
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}
QScrollBar:vertical {{
    background: {CARD};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 6px; background: {CARD}; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QTextEdit, QPlainTextEdit {{
    background: #0a0a10;
    color: #a0ffc8;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    font-family: "SF Mono", Menlo, Monaco, monospace;
    font-size: 11px;
    selection-background-color: {ACCENT};
}}
QLineEdit, QSpinBox {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {CARD_HOV};
    border: none;
    width: 16px;
}}
QPushButton {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
}}
QPushButton:hover  {{ background: {CARD_HOV}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT}; color: white; }}
QPushButton#accent {{
    background: {ACCENT};
    color: white;
    border: none;
}}
QPushButton#accent:hover {{ background: #9180ff; }}
QPushButton#danger {{
    background: transparent;
    color: {RED};
    border: 1px solid {RED};
}}
QPushButton#danger:hover {{ background: {RED}; color: white; }}
QPushButton#success {{
    background: transparent;
    color: {GREEN};
    border: 1px solid {GREEN};
}}
QPushButton#success:hover {{ background: {GREEN}; color: #0d2b22; }}
QLabel#heading {{
    color: {TEXT};
    font-size: 20px;
    font-weight: 600;
}}
QLabel#subheading {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#section {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 8px;
    padding: 12px;
    font-weight: 600;
    color: {TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {TEXT_DIM};
    font-size: 11px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 8px 20px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QDialog {{
    background: {BG};
}}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {CARD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
    color: {TEXT};
}}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
"""


# ── Signals bridge (thread-safe) ─────────────────────────────────────────────

class SignalBridge(QThread):
    log_received       = pyqtSignal(str, str)        # tunnel_id, line
    status_changed     = pyqtSignal(str, object)     # tunnel_id, TunnelStatus
    diagnosis_received = pyqtSignal(str, str, list)  # tunnel_id, problem, fixes


# ── Tunnel card widget ────────────────────────────────────────────────────────

class TunnelCard(QWidget):
    def __init__(self, tunnel: Tunnel, parent=None):
        super().__init__(parent)
        self.tunnel = tunnel
        self._status = TunnelStatus.STOPPED
        self._selected = False
        self.setMinimumHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Row 1: name + status pill
        row1 = QHBoxLayout()
        self._name_lbl = QLabel(self.tunnel.name)
        self._name_lbl.setFont(QFont("SF Pro Display", 13, QFont.Weight.DemiBold))
        self._name_lbl.setStyleSheet(f"color: {TEXT};")

        self._status_pill = QLabel(STATUS_LABELS[self._status])
        self._status_pill.setFont(QFont("SF Pro Display", 10))
        self._status_pill.setStyleSheet(
            f"color: {TEXT_DIM}; background: #3a3a4a; "
            f"border-radius: 8px; padding: 2px 8px;"
        )
        row1.addWidget(self._name_lbl)
        row1.addStretch()
        row1.addWidget(self._status_pill)

        # Row 2: port summary
        ports = "  ".join(
            f":{f.local_port}→{f.remote_port}" for f in self.tunnel.forwards
        )
        self._ports_lbl = QLabel(ports)
        self._ports_lbl.setFont(QFont("SF Mono", 10))
        self._ports_lbl.setStyleSheet(f"color: {TEXT_DIM};")

        # Row 3: jump host
        self._host_lbl = QLabel(
            f"{self.tunnel.jump_host} :{self.tunnel.jump_port}"
        )
        self._host_lbl.setFont(QFont("SF Pro Display", 11))
        self._host_lbl.setStyleSheet(f"color: {TEXT_SUB};")

        layout.addLayout(row1)
        layout.addWidget(self._ports_lbl)
        layout.addWidget(self._host_lbl)
        self._refresh_style()

    def set_status(self, status: TunnelStatus):
        self._status = status
        bg, fg = STATUS_COLORS[status]
        self._status_pill.setText(STATUS_LABELS[status])
        self._status_pill.setStyleSheet(
            f"color: {fg}; background: {bg}; "
            f"border-radius: 8px; padding: 2px 8px;"
        )

    def set_selected(self, sel: bool):
        self._selected = sel
        self._refresh_style()

    def _refresh_style(self):
        if self._selected:
            self.setStyleSheet(
                f"background: {CARD_HOV}; border-left: 3px solid {ACCENT}; border-radius: 10px;"
            )
        else:
            self.setStyleSheet(
                f"background: transparent; border-left: 3px solid transparent; border-radius: 10px;"
            )

    def update_tunnel(self, tunnel: Tunnel):
        self.tunnel = tunnel
        self._name_lbl.setText(tunnel.name)
        ports = "  ".join(
            f":{f.local_port}→{f.remote_port}" for f in tunnel.forwards
        )
        self._ports_lbl.setText(ports)
        self._host_lbl.setText(f"{tunnel.jump_host} :{tunnel.jump_port}")


# ── Forward rule row (used in edit dialog) ───────────────────────────────────

class ForwardRuleRow(QWidget):
    removed = pyqtSignal(object)

    def __init__(self, rule: ForwardRule = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.local_port  = QSpinBox(); self.local_port.setRange(1, 65535)
        self.remote_host = QLineEdit(); self.remote_host.setPlaceholderText("remote host / IP")
        self.remote_port = QSpinBox(); self.remote_port.setRange(1, 65535)
        btn_del = QToolButton()
        btn_del.setText("✕")
        btn_del.setStyleSheet(f"color: {RED}; background: transparent; border: none; font-size: 14px;")
        btn_del.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(QLabel("Local:")); layout.addWidget(self.local_port)
        layout.addWidget(QLabel("→  Host:")); layout.addWidget(self.remote_host, 2)
        layout.addWidget(QLabel(":")); layout.addWidget(self.remote_port)
        layout.addWidget(btn_del)

        if rule:
            self.local_port.setValue(rule.local_port)
            self.remote_host.setText(rule.remote_host)
            self.remote_port.setValue(rule.remote_port)

    def get_rule(self) -> ForwardRule:
        return ForwardRule(
            local_port=self.local_port.value(),
            remote_host=self.remote_host.text().strip(),
            remote_port=self.remote_port.value(),
        )


# ── Tunnel edit / add dialog ──────────────────────────────────────────────────

class TunnelDialog(QDialog):
    def __init__(self, tunnel: Tunnel = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tunnel" if tunnel else "New Tunnel")
        self.setMinimumWidth(600)
        self.setStyleSheet(STYLESHEET)
        self._rule_rows: list[ForwardRuleRow] = []
        self._build(tunnel)

    def _build(self, t: Tunnel):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # title
        title = QLabel("Edit Tunnel" if t else "New Tunnel")
        title.setObjectName("heading")
        layout.addWidget(title)

        # basic fields
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.f_name = QLineEdit(t.name if t else "")
        self.f_name.setPlaceholderText("e.g. ClickHouse Prod")
        self.f_host = QLineEdit(t.jump_host if t else "user@localhost")
        self.f_port = QSpinBox(); self.f_port.setRange(1, 65535)
        self.f_port.setValue(t.jump_port if t else 22)
        self.f_notes = QLineEdit(t.notes if t else "")
        self.f_notes.setPlaceholderText("optional notes")
        self.f_ka_interval = QSpinBox(); self.f_ka_interval.setRange(5, 300)
        self.f_ka_interval.setValue(t.keepalive_interval if t else 30)
        self.f_ka_max = QSpinBox(); self.f_ka_max.setRange(1, 20)
        self.f_ka_max.setValue(t.keepalive_count_max if t else 3)
        self.f_enabled = QCheckBox("Enabled")
        self.f_enabled.setChecked(t.enabled if t else True)

        form.addRow("Name:", self.f_name)
        form.addRow("Jump Host:", self.f_host)
        form.addRow("Jump Port:", self.f_port)
        form.addRow("Notes:", self.f_notes)
        form.addRow("Keepalive Interval (s):", self.f_ka_interval)
        form.addRow("Keepalive Count Max:", self.f_ka_max)
        form.addRow("", self.f_enabled)
        layout.addLayout(form)

        # forward rules
        fwd_group = QGroupBox("Port Forwards")
        fwd_layout = QVBoxLayout(fwd_group)
        fwd_layout.setSpacing(6)
        self._fwd_container = QWidget()
        self._fwd_layout = QVBoxLayout(self._fwd_container)
        self._fwd_layout.setContentsMargins(0, 0, 0, 0)
        self._fwd_layout.setSpacing(4)
        fwd_layout.addWidget(self._fwd_container)

        if t:
            for rule in t.forwards:
                self._add_rule_row(rule)
        else:
            self._add_rule_row()

        btn_add_fwd = QPushButton("+ Add Forward Rule")
        btn_add_fwd.setObjectName("accent")
        btn_add_fwd.clicked.connect(lambda: self._add_rule_row())
        fwd_layout.addWidget(btn_add_fwd)
        layout.addWidget(fwd_group)

        # buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Save")
        ok_btn.setObjectName("accent")
        layout.addWidget(btns)

    def _add_rule_row(self, rule: ForwardRule = None):
        row = ForwardRuleRow(rule)
        row.removed.connect(self._remove_rule_row)
        self._fwd_layout.addWidget(row)
        self._rule_rows.append(row)

    def _remove_rule_row(self, row: ForwardRuleRow):
        self._fwd_layout.removeWidget(row)
        row.deleteLater()
        self._rule_rows.remove(row)

    def get_tunnel(self, existing_id: str = None) -> Tunnel:
        import uuid
        forwards = [r.get_rule() for r in self._rule_rows
                    if r.remote_host.text().strip()]
        return Tunnel(
            id=existing_id or str(uuid.uuid4()),
            name=self.f_name.text().strip() or "Unnamed",
            jump_host=self.f_host.text().strip(),
            jump_port=self.f_port.value(),
            forwards=forwards,
            keepalive_interval=self.f_ka_interval.value(),
            keepalive_count_max=self.f_ka_max.value(),
            enabled=self.f_enabled.isChecked(),
            notes=self.f_notes.text().strip(),
        )


# ── Detail panel (right side) ────────────────────────────────────────────────

class DetailPanel(QWidget):
    request_start  = pyqtSignal(str)
    request_stop   = pyqtSignal(str)
    request_edit   = pyqtSignal(str)
    request_delete = pyqtSignal(str)
    request_clear_log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tunnel: Tunnel = None
        self._status = TunnelStatus.STOPPED
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # header
        self._title = QLabel("Select a tunnel")
        self._title.setObjectName("heading")
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("subheading")
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)

        # action buttons
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("success")
        self._btn_stop  = QPushButton("■  Stop")
        self._btn_stop.setObjectName("danger")
        self._btn_edit  = QPushButton("✎  Edit")
        self._btn_delete = QPushButton("⌫  Delete")
        self._btn_delete.setObjectName("danger")
        for b in [self._btn_start, self._btn_stop, self._btn_edit, self._btn_delete]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        self._btn_start.clicked.connect(lambda: self.request_start.emit(self._tunnel.id))
        self._btn_stop.clicked.connect(lambda:  self.request_stop.emit(self._tunnel.id))
        self._btn_edit.clicked.connect(lambda:  self.request_edit.emit(self._tunnel.id))
        self._btn_delete.clicked.connect(lambda: self.request_delete.emit(self._tunnel.id))
        layout.addLayout(btn_row)

        # tabs: Info | Log
        tabs = QTabWidget()

        # -- Info tab
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 12, 0, 0)
        info_layout.setSpacing(12)

        # status card
        self._status_card = QFrame()
        self._status_card.setStyleSheet(
            f"background: {CARD}; border-radius: 10px; border: 1px solid {BORDER};"
        )
        sc_layout = QHBoxLayout(self._status_card)
        sc_layout.setContentsMargins(16, 12, 16, 12)
        self._status_dot  = QLabel("●")
        self._status_dot.setFont(QFont("SF Pro Display", 22))
        self._status_text = QLabel("Stopped")
        self._status_text.setFont(QFont("SF Pro Display", 16, QFont.Weight.DemiBold))
        self._pid_lbl = QLabel("")
        self._pid_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        sc_layout.addWidget(self._status_dot)
        vv = QVBoxLayout()
        vv.addWidget(self._status_text)
        vv.addWidget(self._pid_lbl)
        sc_layout.addLayout(vv)
        sc_layout.addStretch()
        info_layout.addWidget(self._status_card)

        # ── Error diagnosis card (hidden until an error occurs) ──────────────
        self._diag_card = QFrame()
        self._diag_card.setStyleSheet(
            f"background: #1e0e0e; border: 1px solid {RED}; border-radius: 10px;"
        )
        diag_outer = QVBoxLayout(self._diag_card)
        diag_outer.setContentsMargins(14, 12, 14, 12)
        diag_outer.setSpacing(6)

        diag_header = QHBoxLayout()
        diag_icon = QLabel("✕")
        diag_icon.setStyleSheet(f"color: {RED}; font-size: 18px; font-weight: bold;")
        diag_title = QLabel("Connection Failed")
        diag_title.setFont(QFont("SF Pro Display", 13, QFont.Weight.DemiBold))
        diag_title.setStyleSheet(f"color: {RED};")
        self._btn_retry = QPushButton("↺  Retry")
        self._btn_retry.setObjectName("success")
        self._btn_retry.setFixedHeight(28)
        self._btn_retry.clicked.connect(
            lambda: self._tunnel and self.request_start.emit(self._tunnel.id)
        )
        diag_header.addWidget(diag_icon)
        diag_header.addWidget(diag_title)
        diag_header.addStretch()
        diag_header.addWidget(self._btn_retry)
        diag_outer.addLayout(diag_header)

        # scrollable problem + fix area
        self._diag_body = QWidget()
        self._diag_body_layout = QVBoxLayout(self._diag_body)
        self._diag_body_layout.setContentsMargins(0, 0, 0, 0)
        self._diag_body_layout.setSpacing(4)
        diag_scroll = QScrollArea()
        diag_scroll.setWidgetResizable(True)
        diag_scroll.setWidget(self._diag_body)
        diag_scroll.setFixedHeight(130)
        diag_scroll.setStyleSheet("border: none; background: transparent;")
        diag_outer.addWidget(diag_scroll)
        self._diag_card.setVisible(False)
        info_layout.addWidget(self._diag_card)

        # forwards table
        self._fwd_group = QGroupBox("Port Forwards")
        self._fwd_grid = QGridLayout(self._fwd_group)
        self._fwd_grid.setSpacing(6)
        info_layout.addWidget(self._fwd_group)

        # details
        self._details_group = QGroupBox("Connection Details")
        dg_layout = QFormLayout(self._details_group)
        dg_layout.setSpacing(8)
        self._lbl_host  = QLabel()
        self._lbl_port  = QLabel()
        self._lbl_ka    = QLabel()
        self._lbl_notes = QLabel()
        self._lbl_notes.setWordWrap(True)
        for lbl in [self._lbl_host, self._lbl_port, self._lbl_ka, self._lbl_notes]:
            lbl.setStyleSheet(f"color: {TEXT}; font-family: 'SF Mono', Menlo, monospace; font-size: 12px;")
        dg_layout.addRow("Jump host:", self._lbl_host)
        dg_layout.addRow("Jump port:", self._lbl_port)
        dg_layout.addRow("Keepalive:", self._lbl_ka)
        dg_layout.addRow("Notes:", self._lbl_notes)
        info_layout.addWidget(self._details_group)
        info_layout.addStretch()
        tabs.addTab(info_widget, "Info")

        # -- Log tab
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 8, 0, 0)
        log_layout.setSpacing(6)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(2000)
        btn_clear = QPushButton("Clear Log")
        btn_clear.clicked.connect(lambda: self._on_clear_log())
        log_layout.addWidget(self._log_view)
        log_layout.addWidget(btn_clear)
        tabs.addTab(log_widget, "Log")

        layout.addWidget(tabs, 1)
        self._tabs = tabs
        self._set_enabled(False)

    def _on_clear_log(self):
        self._log_view.clear()
        if self._tunnel:
            self.request_clear_log.emit(self._tunnel.id)

    def load_tunnel(self, tunnel: Tunnel, status: TunnelStatus, pid=None):
        self._tunnel = tunnel
        self._status = status
        self._title.setText(tunnel.name)
        self._subtitle.setText(
            f"{len(tunnel.forwards)} forward(s)  ·  {tunnel.jump_host}:{tunnel.jump_port}"
        )
        self._update_status_card(status, pid)
        self._refresh_forwards()
        self._lbl_host.setText(tunnel.jump_host)
        self._lbl_port.setText(str(tunnel.jump_port))
        self._lbl_ka.setText(
            f"interval {tunnel.keepalive_interval}s, max {tunnel.keepalive_count_max}"
        )
        self._lbl_notes.setText(tunnel.notes or "—")
        self._set_enabled(True)

    def _refresh_forwards(self):
        # clear old
        while self._fwd_grid.count():
            item = self._fwd_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        headers = ["Local port", "→", "Remote host", "Remote port"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600;")
            self._fwd_grid.addWidget(lbl, 0, col)
        for row, fwd in enumerate(self._tunnel.forwards, start=1):
            for col, val in enumerate([
                f":{fwd.local_port}", "→", fwd.remote_host, f":{fwd.remote_port}"
            ]):
                lbl = QLabel(val)
                lbl.setStyleSheet(
                    f"color: {TEXT}; font-family: 'SF Mono', Menlo, monospace; font-size: 12px;"
                )
                self._fwd_grid.addWidget(lbl, row, col)

    def _update_status_card(self, status: TunnelStatus, pid=None):
        self._status = status
        _, fg = STATUS_COLORS[status]
        self._status_dot.setStyleSheet(f"color: {fg};")
        self._status_text.setText(status.value.title())
        self._status_text.setStyleSheet(f"color: {fg}; font-size: 16px; font-weight: 600;")
        self._pid_lbl.setText(f"PID {pid}" if pid else "")
        self._btn_start.setEnabled(status in (TunnelStatus.STOPPED, TunnelStatus.ERROR))
        self._btn_stop.setEnabled(status in (TunnelStatus.CONNECTED, TunnelStatus.STARTING, TunnelStatus.ERROR))
        # hide diagnosis card when no longer in error
        if status != TunnelStatus.ERROR:
            self._diag_card.setVisible(False)

    def show_diagnosis(self, problem: str, fixes: list[str]):
        """Populate and show the diagnosis card in the Info tab."""
        # clear old content
        while self._diag_body_layout.count():
            item = self._diag_body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # problem line
        prob_lbl = QLabel(f"Problem:  {problem}")
        prob_lbl.setStyleSheet(f"color: {RED}; font-size: 12px; font-weight: 600;")
        prob_lbl.setWordWrap(True)
        self._diag_body_layout.addWidget(prob_lbl)

        if fixes:
            fix_title = QLabel("How to fix:")
            fix_title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600;")
            self._diag_body_layout.addWidget(fix_title)

        for fix in fixes:
            row = QHBoxLayout()
            bullet = QLabel("→")
            bullet.setStyleSheet(f"color: {ORANGE}; font-size: 12px;")
            bullet.setFixedWidth(16)
            fix_lbl = QLabel(fix)
            fix_lbl.setFont(QFont("SF Mono", 11))
            fix_lbl.setStyleSheet(
                f"color: {TEXT}; background: #1a1500; border-radius: 4px; padding: 3px 8px;"
            )
            fix_lbl.setWordWrap(True)
            fix_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            row.addWidget(bullet)
            row.addWidget(fix_lbl, 1)
            w = QWidget()
            w.setLayout(row)
            self._diag_body_layout.addWidget(w)

        self._diag_body_layout.addStretch()
        self._diag_card.setVisible(True)
        # switch to Info tab so user sees it immediately
        self._tabs.setCurrentIndex(0)

    def append_log(self, line: str):
        self._log_view.appendPlainText(line)
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_status(self, status: TunnelStatus, pid=None):
        if self._tunnel:
            self._update_status_card(status, pid)

    def _set_enabled(self, en: bool):
        for w in [self._btn_start, self._btn_stop, self._btn_edit, self._btn_delete]:
            w.setEnabled(en)

    def clear(self):
        self._tunnel = None
        self._title.setText("Select a tunnel")
        self._subtitle.setText("")
        self._set_enabled(False)


# ── Preflight check dialog ───────────────────────────────────────────────────

SEVERITY_ICON = {
    Severity.OK:      ("✓", GREEN),
    Severity.WARNING: ("⚠", ORANGE),
    Severity.ERROR:   ("✕", RED),
}


class _FixWorker(QThread):
    """Runs auto_fix_cmd in a background QThread; emits signals back to main thread."""
    line_ready  = pyqtSignal(str)
    finished    = pyqtSignal(bool, str)

    def __init__(self, result: CheckResult):
        super().__init__()
        self._result = result

    def run(self):
        run_auto_fix(self._result,
                     on_line=lambda l: self.line_ready.emit(l),
                     on_done=lambda ok, m: self.finished.emit(ok, m))
        # block until run_auto_fix's daemon thread finishes
        import time; time.sleep(0.1)


class _RecheckWorker(QThread):
    """Runs all preflight checks off the main thread; emits results when done."""
    done = pyqtSignal(list)

    def run(self):
        from .preflight import run_all_checks
        self.done.emit(run_all_checks())


class PreflightDialog(QDialog):
    """Startup dialog: dependency + connectivity checks before main window opens.

    All subprocess/network calls happen in QThreads so the UI stays responsive.
    Continue is blocked only while ERROR-severity checks remain unresolved.
    """

    def __init__(self, results: list[CheckResult], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Startup Checks")
        self.setMinimumSize(660, 500)
        self.setStyleSheet(STYLESHEET)
        self._results = results
        self._workers: list[QThread] = []   # keep refs so GC doesn't kill them
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Environment Check")
        title.setObjectName("heading")
        subtitle = QLabel(
            "Checking required tools and jump-host connectivity before launch."
        )
        subtitle.setObjectName("subheading")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # scrollable results
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._results_widget)
        scroll.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(scroll, 1)

        # log (shown during auto-fix)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(90)
        self._log.setVisible(False)
        layout.addWidget(self._log)

        # bottom buttons
        btn_row = QHBoxLayout()
        self._btn_recheck = QPushButton("↻  Re-check")
        self._btn_recheck.clicked.connect(self._recheck)
        self._btn_continue = QPushButton("Continue →")
        self._btn_continue.setObjectName("accent")
        self._btn_continue.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_recheck)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_continue)
        layout.addLayout(btn_row)

        self._render_results()

    def _render_results(self):
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_errors = any(r.severity == Severity.ERROR for r in self._results)
        self._btn_continue.setEnabled(not has_errors)

        for result in self._results:
            self._results_layout.addWidget(self._make_result_card(result))
        self._results_layout.addStretch()

    def _make_result_card(self, result: CheckResult) -> QWidget:
        icon, color = SEVERITY_ICON[result.severity]
        bg = {Severity.OK: CARD, Severity.WARNING: "#1e1a0e", Severity.ERROR: "#1e0e0e"}[result.severity]
        card = QFrame()
        card.setStyleSheet(f"background: {bg}; border: 1px solid {BORDER}; border-radius: 10px;")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(4)

        row1 = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        icon_lbl.setFixedWidth(20)
        name_lbl = QLabel(result.name)
        name_lbl.setFont(QFont("SF Pro Display", 13, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {TEXT};")
        row1.addWidget(icon_lbl)
        row1.addWidget(name_lbl)
        row1.addStretch()

        if result.severity != Severity.OK and result.auto_fix_cmd:
            btn_fix = QPushButton("Auto-fix")
            btn_fix.setObjectName("accent")
            btn_fix.setFixedWidth(80)
            btn_fix.setFixedHeight(26)
            btn_fix.setStyleSheet(btn_fix.styleSheet() + "font-size: 11px; padding: 2px 8px;")
            btn_fix.clicked.connect(lambda _, r=result, b=btn_fix: self._run_fix(r, b))
            row1.addWidget(btn_fix)

        cl.addLayout(row1)

        msg_lbl = QLabel(result.message)
        msg_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        msg_lbl.setWordWrap(True)
        cl.addWidget(msg_lbl)

        if result.fix and result.severity != Severity.OK:
            fix_lbl = QLabel(result.fix)
            fix_lbl.setFont(QFont("SF Mono", 10))
            fix_lbl.setStyleSheet(
                f"color: {ORANGE}; background: #1a1500; border-radius: 4px; padding: 4px 8px;"
            )
            fix_lbl.setWordWrap(True)
            cl.addWidget(fix_lbl)

        return card

    def _run_fix(self, result: CheckResult, btn: QPushButton):
        btn.setEnabled(False)
        btn.setText("Running…")
        self._log.setVisible(True)
        self._log.clear()
        self._btn_recheck.setEnabled(False)

        worker = _FixWorker(result)
        self._workers.append(worker)
        worker.line_ready.connect(self._log.appendPlainText)
        worker.finished.connect(lambda ok, msg, b=btn: self._on_fix_done(ok, msg, b))
        worker.start()

    def _on_fix_done(self, ok: bool, msg: str, btn: QPushButton):
        self._log.appendPlainText(msg)
        btn.setText("Done ✓" if ok else "Failed ✕")
        self._btn_recheck.setEnabled(True)

    def _recheck(self):
        self._btn_recheck.setEnabled(False)
        self._btn_continue.setEnabled(False)
        self._btn_recheck.setText("Checking…")
        self._log.setVisible(False)

        worker = _RecheckWorker()
        self._workers.append(worker)
        worker.done.connect(self._on_recheck_done)
        worker.start()

    def _on_recheck_done(self, results: list):
        self._results = results
        self._render_results()
        self._btn_recheck.setEnabled(True)
        self._btn_recheck.setText("↻  Re-check")


# ── SSH Key Manager dialog ───────────────────────────────────────────────────

class SSHKeyManagerDialog(QDialog):
    """Two-tab dialog: 'My Keys' list + 'Generate' form + 'Copy to Server' form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Key Manager")
        self.setMinimumSize(680, 520)
        self.setStyleSheet(STYLESHEET)
        self._build()
        self._refresh_keys()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("SSH Key Manager")
        title.setObjectName("heading")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_keys_tab(),      "My Keys")
        tabs.addTab(self._build_generate_tab(),  "Generate Key")
        tabs.addTab(self._build_copy_tab(),      "Copy to Server")
        layout.addWidget(tabs, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)

    # ── Tab 1: existing keys ─────────────────────────────────────────────────

    def _build_keys_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        hint = QLabel(f"Keys in {SSH_DIR}")
        hint.setObjectName("subheading")
        layout.addWidget(hint)

        self._keys_scroll = QWidget()
        self._keys_layout = QVBoxLayout(self._keys_scroll)
        self._keys_layout.setContentsMargins(0, 0, 0, 0)
        self._keys_layout.setSpacing(6)
        self._keys_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._keys_scroll)
        scroll.setStyleSheet(f"border: none; background: transparent;")
        layout.addWidget(scroll, 1)

        btn_refresh = QPushButton("↻  Refresh")
        btn_refresh.clicked.connect(self._refresh_keys)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn_refresh)
        layout.addLayout(row)
        return w

    def _refresh_keys(self):
        # clear old cards
        while self._keys_layout.count() > 1:
            item = self._keys_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        keys = discover_keys()
        if not keys:
            empty = QLabel("No SSH keys found in ~/.ssh\nUse 'Generate Key' to create one.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._keys_layout.insertWidget(0, empty)
            return

        for key in keys:
            card = self._make_key_card(key)
            self._keys_layout.insertWidget(self._keys_layout.count() - 1, card)

    def _make_key_card(self, key: SSHKey) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        row1 = QHBoxLayout()
        name_lbl = QLabel(key.name)
        name_lbl.setFont(QFont("SF Pro Display", 13, QFont.Weight.DemiBold))
        type_pill = QLabel(key.key_type.upper())
        type_pill.setStyleSheet(
            f"background: {CARD_HOV}; color: {ACCENT}; border-radius: 6px; "
            f"padding: 1px 7px; font-size: 10px; font-weight: 600;"
        )
        row1.addWidget(name_lbl)
        row1.addStretch()
        row1.addWidget(type_pill)

        fp_lbl = QLabel(key.fingerprint or "fingerprint unavailable")
        fp_lbl.setFont(QFont("SF Mono", 10))
        fp_lbl.setStyleSheet(f"color: {TEXT_DIM};")

        pub_lbl = QLabel(key.pub_content[:72] + "…" if len(key.pub_content) > 72 else key.pub_content)
        pub_lbl.setFont(QFont("SF Mono", 10))
        pub_lbl.setStyleSheet(f"color: {TEXT_SUB};")
        pub_lbl.setWordWrap(True)

        btn_copy = QPushButton("Copy public key")
        btn_copy.setFixedWidth(130)
        btn_copy.clicked.connect(
            lambda _, k=key: QApplication.clipboard().setText(k.pub_content)
            or btn_copy.setText("Copied!")
        )

        layout.addLayout(row1)
        layout.addWidget(fp_lbl)
        layout.addWidget(pub_lbl)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_copy)
        layout.addLayout(btn_row)
        return card

    # ── Tab 2: generate ──────────────────────────────────────────────────────

    def _build_generate_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)

        note = QLabel(
            "Generates a new SSH key pair in ~/.ssh.\n"
            "ed25519 is recommended — fast, short keys, strong security."
        )
        note.setObjectName("subheading")
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._gen_type = QListWidget()
        self._gen_type.setFixedHeight(80)
        self._gen_type.setStyleSheet(
            f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;"
        )
        for kt in KEY_TYPES:
            self._gen_type.addItem(kt)
        self._gen_type.setCurrentRow(0)

        self._gen_path = QLineEdit()
        self._gen_path.setText(str(default_key_path("ed25519")))
        self._gen_type.currentRowChanged.connect(
            lambda i: self._gen_path.setText(
                str(default_key_path(KEY_TYPES[i]))
            )
        )

        self._gen_comment = QLineEdit()
        self._gen_comment.setPlaceholderText(f"{os.environ.get('USER', 'user')}@{os.uname().nodename}")
        self._gen_comment.setText(self._gen_comment.placeholderText())

        self._gen_passphrase = QLineEdit()
        self._gen_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self._gen_passphrase.setPlaceholderText("Leave blank for no passphrase")

        form.addRow("Key type:", self._gen_type)
        form.addRow("Save to:", self._gen_path)
        form.addRow("Comment:", self._gen_comment)
        form.addRow("Passphrase:", self._gen_passphrase)
        layout.addLayout(form)

        self._gen_output = QPlainTextEdit()
        self._gen_output.setReadOnly(True)
        self._gen_output.setFixedHeight(80)
        self._gen_output.setPlaceholderText("Output will appear here…")
        layout.addWidget(self._gen_output)

        self._btn_generate = QPushButton("Generate Key")
        self._btn_generate.setObjectName("accent")
        self._btn_generate.clicked.connect(self._do_generate)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._btn_generate)
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    def _do_generate(self):
        from pathlib import Path
        key_path = Path(self._gen_path.text().strip())
        if key_path.exists():
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"{key_path} already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._btn_generate.setEnabled(False)
        self._gen_output.setPlainText("Generating…")

        key_type   = KEY_TYPES[self._gen_type.currentRow()]
        comment    = self._gen_comment.text().strip()
        passphrase = self._gen_passphrase.text()

        def on_done(ok, msg):
            self._btn_generate.setEnabled(True)
            self._gen_output.setPlainText(msg)
            if ok:
                self._refresh_keys()   # update My Keys tab

        generate_key(key_type, key_path, comment, passphrase, on_done)

    # ── Tab 3: copy to server ────────────────────────────────────────────────

    def _build_copy_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)

        note = QLabel(
            "Copies your public key to the remote server using ssh-copy-id.\n"
            "Leave Password blank if you already have key-based access.\n"
            "Password field requires sshpass: brew install sshpass"
        )
        note.setObjectName("subheading")
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # key selector
        self._copy_key_combo = QListWidget()
        self._copy_key_combo.setFixedHeight(80)
        self._copy_key_combo.setStyleSheet(
            f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;"
        )
        self._copy_keys: List[SSHKey] = []
        self._refresh_copy_keys()

        self._copy_user = QLineEdit()
        self._copy_user.setPlaceholderText("username on the remote server")

        self._copy_host = QLineEdit()
        self._copy_host.setPlaceholderText("hostname or IP (e.g. localhost)")

        self._copy_port = QSpinBox()
        self._copy_port.setRange(1, 65535)
        self._copy_port.setValue(22)

        self._copy_password = QLineEdit()
        self._copy_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._copy_password.setPlaceholderText("Optional — only if key auth not yet set up")

        form.addRow("SSH key:", self._copy_key_combo)
        form.addRow("Remote user:", self._copy_user)
        form.addRow("Remote host:", self._copy_host)
        form.addRow("Remote port:", self._copy_port)
        form.addRow("Password:", self._copy_password)
        layout.addLayout(form)

        self._copy_output = QPlainTextEdit()
        self._copy_output.setReadOnly(True)
        self._copy_output.setFixedHeight(100)
        self._copy_output.setPlaceholderText("Output will appear here…")
        layout.addWidget(self._copy_output)

        self._btn_copy_key = QPushButton("Copy Public Key to Server")
        self._btn_copy_key.setObjectName("accent")
        self._btn_copy_key.clicked.connect(self._do_copy_key)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._btn_copy_key)
        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    def _refresh_copy_keys(self):
        self._copy_key_combo.clear()
        self._copy_keys = discover_keys()
        for key in self._copy_keys:
            self._copy_key_combo.addItem(f"{key.name}  ({key.key_type})")
        if self._copy_keys:
            self._copy_key_combo.setCurrentRow(0)

    def _do_copy_key(self):
        idx = self._copy_key_combo.currentRow()
        if idx < 0 or idx >= len(self._copy_keys):
            QMessageBox.warning(self, "No Key", "Select a key first.")
            return
        key  = self._copy_keys[idx]
        user = self._copy_user.text().strip()
        host = self._copy_host.text().strip()
        port = self._copy_port.value()
        pwd  = self._copy_password.text() or None

        if not user or not host:
            QMessageBox.warning(self, "Missing Fields", "Remote user and host are required.")
            return

        self._btn_copy_key.setEnabled(False)
        self._copy_output.clear()

        def on_progress(line):
            self._copy_output.appendPlainText(line)

        def on_done(ok, msg):
            self._btn_copy_key.setEnabled(True)
            self._copy_output.appendPlainText(msg)

        copy_key_to_server(key.private_path, user, host, port, pwd, on_progress, on_done)


# ── Sidebar tunnel list ──────────────────────────────────────────────────────

class SidebarList(QWidget):
    tunnel_selected  = pyqtSignal(str)
    add_requested    = pyqtSignal()
    start_all        = pyqtSignal()
    stop_all         = pyqtSignal()
    ssh_keys_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self._cards: dict[str, TunnelCard] = {}   # tunnel_id -> card
        self._items: dict[str, QListWidgetItem] = {}
        self._selected_id: str = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # top bar
        topbar = QWidget()
        topbar.setStyleSheet(f"background: {SIDEBAR};")
        topbar.setFixedHeight(56)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        app_lbl = QLabel("DB Tunnels")
        app_lbl.setFont(QFont("SF Pro Display", 14, QFont.Weight.Bold))
        app_lbl.setStyleSheet(f"color: {TEXT};")
        btn_add = QToolButton()
        btn_add.setText("+")
        btn_add.setFont(QFont("SF Pro Display", 18, QFont.Weight.Light))
        btn_add.setStyleSheet(
            f"color: {ACCENT}; background: transparent; border: none; font-size: 22px;"
        )
        btn_add.setToolTip("Add new tunnel")
        btn_add.clicked.connect(self.add_requested)
        btn_keys = QToolButton()
        btn_keys.setText("🔑")
        btn_keys.setToolTip("SSH Key Manager")
        btn_keys.setStyleSheet(
            f"background: transparent; border: none; font-size: 16px;"
        )
        btn_keys.clicked.connect(self.ssh_keys_requested)
        tb_layout.addWidget(app_lbl)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_keys)
        tb_layout.addWidget(btn_add)
        layout.addWidget(topbar)

        # bulk actions
        bulk = QWidget()
        bulk.setStyleSheet(f"background: {SIDEBAR};")
        bl = QHBoxLayout(bulk)
        bl.setContentsMargins(10, 4, 10, 8)
        bl.setSpacing(6)
        btn_all_start = QPushButton("▶ All")
        btn_all_stop  = QPushButton("■ All")
        btn_all_start.setObjectName("success")
        btn_all_stop.setObjectName("danger")
        btn_all_start.setFixedHeight(28)
        btn_all_stop.setFixedHeight(28)
        btn_all_start.setStyleSheet(
            btn_all_start.styleSheet() +
            "font-size: 11px; padding: 2px 10px;"
        )
        btn_all_stop.setStyleSheet(
            btn_all_stop.styleSheet() +
            "font-size: 11px; padding: 2px 10px;"
        )
        btn_all_start.clicked.connect(self.start_all)
        btn_all_stop.clicked.connect(self.stop_all)
        bl.addWidget(btn_all_start)
        bl.addWidget(btn_all_stop)
        bl.addStretch()
        layout.addWidget(bulk)

        # divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        layout.addWidget(div)

        # list
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {SIDEBAR};
                border: none;
                outline: none;
                padding: 6px;
            }}
            QListWidget::item {{
                background: transparent;
                border-radius: 10px;
                padding: 0;
                margin: 2px 0;
            }}
            QListWidget::item:selected {{
                background: transparent;
            }}
        """)
        self._list.setSpacing(2)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

    def add_tunnel(self, tunnel: Tunnel):
        item = QListWidgetItem(self._list)
        card = TunnelCard(tunnel)
        item.setSizeHint(QSize(0, 100))
        self._list.addItem(item)
        self._list.setItemWidget(item, card)
        self._cards[tunnel.id] = card
        self._items[tunnel.id] = item

    def update_tunnel(self, tunnel: Tunnel):
        if tunnel.id in self._cards:
            self._cards[tunnel.id].update_tunnel(tunnel)

    def remove_tunnel(self, tunnel_id: str):
        if tunnel_id not in self._items:
            return
        item = self._items.pop(tunnel_id)
        row = self._list.row(item)
        self._list.takeItem(row)
        self._cards.pop(tunnel_id, None)

    def set_status(self, tunnel_id: str, status: TunnelStatus):
        if tunnel_id in self._cards:
            self._cards[tunnel_id].set_status(status)

    def _on_item_clicked(self, item: QListWidgetItem):
        for tid, it in self._items.items():
            selected = it is item
            self._cards[tid].set_selected(selected)
            if selected:
                self._selected_id = tid
                self.tunnel_selected.emit(tid)

    def select_tunnel(self, tunnel_id: str):
        if tunnel_id in self._items:
            item = self._items[tunnel_id]
            self._on_item_clicked(item)


# ── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DB Tunnels")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)

        self._tunnels: dict[str, Tunnel] = {}
        self._logs: dict[str, list[str]] = {}  # per-tunnel log buffer

        # thread-safe signal bridge
        self._bridge = SignalBridge()
        self._bridge.log_received.connect(self._on_log)
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.diagnosis_received.connect(self._on_diagnosis)
        self._bridge.start()

        self._manager = TunnelManager(
            on_log=lambda tid, line: self._bridge.log_received.emit(tid, line),
            on_status=lambda tid, st: self._bridge.status_changed.emit(tid, st),
            on_diagnosis=lambda tid, prob, fixes: self._bridge.diagnosis_received.emit(tid, prob, fixes),
        )

        self._build_ui()
        self._load_tunnels()

    def _build_ui(self):
        self.setStyleSheet(STYLESHEET)
        central = QWidget()
        self.setCentralWidget(central)

        # transparent title bar feel on mac
        self.setUnifiedTitleAndToolBarOnMac(True)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = SidebarList()
        self._sidebar.tunnel_selected.connect(self._on_tunnel_selected)
        self._sidebar.add_requested.connect(self._on_add)
        self._sidebar.start_all.connect(self._on_start_all)
        self._sidebar.stop_all.connect(self._on_stop_all)
        self._sidebar.ssh_keys_requested.connect(self._on_ssh_keys)

        self._detail = DetailPanel()
        self._detail.request_start.connect(self._on_start)
        self._detail.request_stop.connect(self._on_stop)
        self._detail.request_edit.connect(self._on_edit)
        self._detail.request_delete.connect(self._on_delete)
        self._detail.request_clear_log.connect(lambda tid: self._logs.pop(tid, None))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._detail)
        splitter.setSizes([280, 820])
        splitter.setHandleWidth(1)

        main_layout.addWidget(splitter)

    def _load_tunnels(self):
        tunnels = load_tunnels()
        for t in tunnels:
            self._tunnels[t.id] = t
            self._logs[t.id] = []
            self._sidebar.add_tunnel(t)
        # auto-select first
        if tunnels:
            self._sidebar.select_tunnel(tunnels[0].id)

    def _on_tunnel_selected(self, tunnel_id: str):
        t = self._tunnels.get(tunnel_id)
        if not t:
            return
        status = self._manager.status(tunnel_id)
        pid    = self._manager.pid(tunnel_id)
        self._detail.load_tunnel(t, status, pid)
        # replay buffered logs
        self._detail._log_view.clear()
        for line in self._logs.get(tunnel_id, []):
            self._detail._log_view.appendPlainText(line)

    def _on_log(self, tunnel_id: str, line: str):
        if tunnel_id not in self._logs:
            self._logs[tunnel_id] = []
        self._logs[tunnel_id].append(line)
        # only update UI if this tunnel is currently visible
        if self._detail._tunnel and self._detail._tunnel.id == tunnel_id:
            self._detail.append_log(line)

    def _on_status_changed(self, tunnel_id: str, status: TunnelStatus):
        self._sidebar.set_status(tunnel_id, status)
        if self._detail._tunnel and self._detail._tunnel.id == tunnel_id:
            pid = self._manager.pid(tunnel_id)
            self._detail.update_status(status, pid)

    def _on_diagnosis(self, tunnel_id: str, problem: str, fixes: list):
        if self._detail._tunnel and self._detail._tunnel.id == tunnel_id:
            self._detail.show_diagnosis(problem, fixes)

    def _on_start(self, tunnel_id: str):
        t = self._tunnels.get(tunnel_id)
        if t:
            self._manager.start(t)

    def _on_stop(self, tunnel_id: str):
        self._manager.stop(tunnel_id)

    def _on_start_all(self):
        for t in self._tunnels.values():
            if t.enabled:
                self._manager.start(t)

    def _on_stop_all(self):
        self._manager.stop_all()

    def _on_ssh_keys(self):
        dlg = SSHKeyManagerDialog(parent=self)
        dlg.exec()

    def _on_add(self):
        dlg = TunnelDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t = dlg.get_tunnel()
            self._tunnels[t.id] = t
            self._logs[t.id] = []
            self._sidebar.add_tunnel(t)
            self._save()
            self._sidebar.select_tunnel(t.id)

    def _on_edit(self, tunnel_id: str):
        t = self._tunnels.get(tunnel_id)
        if not t:
            return
        dlg = TunnelDialog(tunnel=t, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_tunnel(existing_id=tunnel_id)
            self._tunnels[tunnel_id] = updated
            self._sidebar.update_tunnel(updated)
            self._detail.load_tunnel(updated, self._manager.status(tunnel_id), self._manager.pid(tunnel_id))
            self._save()

    def _on_delete(self, tunnel_id: str):
        t = self._tunnels.get(tunnel_id)
        if not t:
            return
        reply = QMessageBox.question(
            self, "Delete Tunnel",
            f"Delete '{t.name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._manager.remove(tunnel_id)
        del self._tunnels[tunnel_id]
        self._logs.pop(tunnel_id, None)
        self._sidebar.remove_tunnel(tunnel_id)
        self._detail.clear()
        self._save()
        # select next available
        remaining = list(self._tunnels.keys())
        if remaining:
            self._sidebar.select_tunnel(remaining[0])

    def _save(self):
        save_tunnels(list(self._tunnels.values()))

    def closeEvent(self, event):
        self._manager.stop_all()
        event.accept()


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DB Tunnels")
    app.setOrganizationName("DBTunnels")

    # macOS dark mode
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base,            QColor(CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(CARD_HOV))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button,          QColor(CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    # Run preflight checks — always show dialog in bundled .app, otherwise only on failure
    results = run_all_checks()
    is_bundled = getattr(sys, "frozen", False)
    if is_bundled or any(r.severity != Severity.OK for r in results):
        dlg = PreflightDialog(results)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)   # user closed dialog with unresolved errors

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
