#!/usr/bin/env python3
"""
PySide6 prototype for a Binance-style trading terminal.
This UI is disconnected from the actual bot logic and serves purely as a design playground.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from PySide6 import QtCore, QtGui, QtWidgets


class ControlPanel(QtWidgets.QFrame):
    """Top control panel with account summary, strictness slider and risk selector."""

    strictnessChanged = QtCore.Signal(float)
    riskRatioChanged = QtCore.Signal(float)
    connectionToggled = QtCore.Signal(bool)
    autoTradingToggled = QtCore.Signal(bool)
    refreshRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ControlPanel")
        self.setMinimumHeight(52)
        self.setMaximumHeight(60)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # === LEFT: Critical trading metrics in one clean row ===
        metrics_layout = QtWidgets.QHBoxLayout()
        metrics_layout.setSpacing(16)

        # Core account metrics
        self.balance_label = self._metric_label("Баланс", "$10,450", "accent")
        self.pnl_label = self._metric_label("Прибыль (день)", "+$342", "positive")
        self.winrate_label = self._metric_label("Винрейт", "62%", "accent")
        
        # Risk metrics
        self.margin_label = self._metric_label("Маржа", "35%", "muted")
        self.drawdown_label = self._metric_label("Просадка", "2.4%", "muted")
        self.positions_label = self._metric_label("Открыто", "4 поз.", "muted")

        metrics_layout.addWidget(self.balance_label)
        metrics_layout.addWidget(self.pnl_label)
        metrics_layout.addWidget(self.winrate_label)
        metrics_layout.addSpacing(30)
        metrics_layout.addWidget(self.margin_label)
        metrics_layout.addWidget(self.drawdown_label)
        metrics_layout.addWidget(self.positions_label)
        metrics_layout.addStretch()

        layout.addLayout(metrics_layout)

        layout.addSpacing(20)

        # === RIGHT: Compact action buttons ===
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.connection_button = QtWidgets.QPushButton("Подключить")
        self.connection_button.setObjectName("PrimaryButton")
        self.connection_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.connection_button.setCheckable(True)
        self.connection_button.setMinimumHeight(36)
        self.connection_button.setFixedWidth(110)
        buttons_layout.addWidget(self.connection_button)

        self.auto_button = QtWidgets.QPushButton("Авто ВЫКЛ")
        self.auto_button.setObjectName("SecondaryButton")
        self.auto_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.auto_button.setCheckable(True)
        self.auto_button.setMinimumHeight(36)
        self.auto_button.setFixedWidth(110)
        buttons_layout.addWidget(self.auto_button)

        self.refresh_button = QtWidgets.QPushButton("⟳")
        self.refresh_button.setObjectName("GhostButton")
        self.refresh_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setMinimumHeight(36)
        self.refresh_button.setFixedWidth(36)
        buttons_layout.addWidget(self.refresh_button)

        layout.addLayout(buttons_layout)

        # Wire signals
        self.connection_button.toggled.connect(self._on_connection_toggled)
        self.auto_button.toggled.connect(self._on_auto_trading_toggled)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)

        self._update_connection_button_text(False)
        self._update_auto_button_text(False)

    def _stat_chip(self, title: str, value: str) -> QtWidgets.QFrame:
        chip = QtWidgets.QFrame()
        chip.setObjectName("StatChip")
        chip.setMinimumWidth(80)
        chip.setMaximumWidth(120)
        chip.setMinimumHeight(45)
        chip_layout = QtWidgets.QVBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 8, 4)
        chip_layout.setSpacing(1)
        title_label = QtWidgets.QLabel(title.upper())
        title_label.setObjectName("StatTitle")
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("StatValue")
        chip_layout.addWidget(title_label)
        chip_layout.addWidget(value_label)
        return chip

    def _metric_label(self, title: str, value: str, accent_role: str = "accent") -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        container.setObjectName("Metric")
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        container.setMinimumWidth(100)
        container.setMaximumWidth(140)
        container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)

        title_label = QtWidgets.QLabel(title.upper())
        title_label.setObjectName("MetricTitle")
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("MetricValue")
        value_label.setProperty("accentRole", accent_role)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return container

    @QtCore.Slot(int)
    def _on_strictness_changed(self, value: int) -> None:
        if value <= 30:
            mode = "Relaxed"
        elif value <= 60:
            mode = "Moderate"
        else:
            mode = "Strict"
        self.strictness_value_label.setText(f"{value}% • {mode}")
        self.strictnessChanged.emit(float(value))

    @QtCore.Slot(str)
    def _on_risk_ratio_changed(self, text: str) -> None:
        try:
            ratio = float(text.split(":")[1])
        except Exception:
            ratio = 2.0
        self.riskRatioChanged.emit(ratio)

    def update_balance(self, balance: float) -> None:
        value_label = self.balance_label.findChild(QtWidgets.QLabel, "MetricValue")
        value_label.setText(f"${balance:,.0f}")

    def update_pnl(self, pnl: float) -> None:
        value_label = self.pnl_label.findChild(QtWidgets.QLabel, "MetricValue")
        sign = "+" if pnl >= 0 else ""
        value_label.setText(f"{sign}${pnl:,.0f}")
        value_label.setProperty("accentRole", "positive" if pnl >= 0 else "negative")
        self._refresh_widget(value_label)

    def update_winrate(self, winrate: float) -> None:
        value_label = self.winrate_label.findChild(QtWidgets.QLabel, "MetricValue")
        value_label.setText(f"{winrate:.0f}%")
    
    def update_risk_metrics(self, margin_used: float, drawdown: float, positions_count: int) -> None:
        margin_value = self.margin_label.findChild(QtWidgets.QLabel, "MetricValue")
        drawdown_value = self.drawdown_label.findChild(QtWidgets.QLabel, "MetricValue")
        positions_value = self.positions_label.findChild(QtWidgets.QLabel, "MetricValue")
        
        margin_value.setText(f"{margin_used:.0f}%")
        drawdown_value.setText(f"{drawdown:.1f}%")
        positions_value.setText(f"{positions_count} поз.")

    def set_connection_toggle_state(self, connected: bool, silent: bool = False) -> None:
        if silent:
            self.connection_button.blockSignals(True)
        self.connection_button.setChecked(connected)
        self._update_connection_button_text(connected)
        if silent:
            self.connection_button.blockSignals(False)

    def set_auto_trading_state(self, active: bool, silent: bool = False) -> None:
        if silent:
            self.auto_button.blockSignals(True)
        self.auto_button.setChecked(active)
        self._update_auto_button_text(active)
        if silent:
            self.auto_button.blockSignals(False)



    def _on_connection_toggled(self, checked: bool) -> None:
        self._update_connection_button_text(checked)
        self.connectionToggled.emit(checked)

    def _on_auto_trading_toggled(self, checked: bool) -> None:
        self._update_auto_button_text(checked)
        self.autoTradingToggled.emit(checked)

    def _on_refresh_clicked(self) -> None:
        self.refreshRequested.emit()

    def _update_connection_button_text(self, connected: bool) -> None:
        self.connection_button.setText("Отключить" if connected else "Подключить")
        self.connection_button.setProperty("active", "true" if connected else "false")
        self._refresh_widget(self.connection_button)

    def _update_auto_button_text(self, active: bool) -> None:
        self.auto_button.setText("Авто ВКЛ" if active else "Авто ВЫКЛ")
        self.auto_button.setProperty("active", "true" if active else "false")
        self._refresh_widget(self.auto_button)

    @staticmethod
    def _refresh_widget(widget: QtWidgets.QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


class MockTable(QtWidgets.QTableWidget):
    """Reusable table with Binance-inspired styling."""

    def __init__(self, rows: int, columns: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setObjectName("DataTable")
        self.horizontalHeader().setObjectName("TableHeader")
        self.setMouseTracking(True)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)


class SignalsWidget(MockTable):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["Пара", "Направление", "Уверенность", "Комментарий"])
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        # Don't populate mock data - wait for real data from bot
        self.setSortingEnabled(True)

    def populate_mock_data(self):
        self.setSortingEnabled(False)
        sample = [
            ("BTCUSDT", "LONG", 73, "Strong support at 10200"),
            ("ETHUSDT", "SHORT", 65, "Heavy Ask at 3450"),
            ("SOLUSDT", "WAIT", 48, "Flat spread"),
            ("XRPUSDT", "LONG", 58, "Momentum rising"),
            ("NEARUSDT", "LONG", 81, "Fib 0.618 match"),
            ("AVAXUSDT", "WAIT", 42, "No aggression"),
        ]
        self.setRowCount(len(sample))
        for row, (symbol, direction, confidence, comment) in enumerate(sample):
            direction_item = QtWidgets.QTableWidgetItem(direction)
            if direction == "LONG":
                direction_item.setForeground(QtGui.QColor("#0ECB81"))
            elif direction == "SHORT":
                direction_item.setForeground(QtGui.QColor("#F6465D"))
            self.setItem(row, 0, QtWidgets.QTableWidgetItem(symbol))
            self.setItem(row, 1, direction_item)
            self.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{confidence:.0f}%"))
            self.setItem(row, 3, QtWidgets.QTableWidgetItem(comment))
            self.setRowHidden(row, False)
        self.setSortingEnabled(True)

    def highlight_symbol(self, symbol: str):
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if not item:
                continue
            font = item.font()
            if item.text() == symbol:
                font.setBold(True)
                highlight_brush = QtGui.QBrush(QtGui.QColor(240, 185, 11, 60))
            else:
                font.setBold(False)
                highlight_brush = QtGui.QBrush(QtCore.Qt.GlobalColor.transparent)
            for col in range(self.columnCount()):
                cell = self.item(row, col)
                if cell:
                    cell.setFont(font)
                    cell.setBackground(highlight_brush)

    def get_symbol(self, row: int) -> str | None:
        if row < 0 or row >= self.rowCount():
            return None
        item = self.item(row, 0)
        return item.text() if item else None

    def filter_rows(self, search_text: str, include_directions: set[str]) -> None:
        search_value = (search_text or "").strip().lower()
        for row in range(self.rowCount()):
            symbol_item = self.item(row, 0)
            direction_item = self.item(row, 1)
            comment_item = self.item(row, 3)
            if not direction_item:
                self.setRowHidden(row, True)
                continue
            direction = direction_item.text().upper()
            matches_direction = direction in include_directions if include_directions else False
            if search_value:
                matches_text = any(
                    search_value in (item.text().lower() if item else "")
                    for item in (symbol_item, comment_item)
                )
            else:
                matches_text = True
            self.setRowHidden(row, not (matches_direction and matches_text))

    def visible_row_count(self) -> int:
        return sum(1 for row in range(self.rowCount()) if not self.isRowHidden(row))

    def first_visible_row(self) -> int | None:
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                return row
        return None


class PositionsWidget(MockTable):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 9, parent)
        self.setHorizontalHeaderLabels(["Пара", "Напр.", "Вход", "Текущая", "Размер", "SL", "TP", "PNL", "R:R"])
        # Don't populate mock data - wait for real data from bot
        self.setSortingEnabled(True)

    def populate_mock_data(self):
        self.setSortingEnabled(False)
        sample = [
            ("BTCUSDT", "LONG", 10210.5, 10248.7, 0.12, 10185.0, 10270.0, 420.4, "1:2.5"),
            ("ETHUSDT", "SHORT", 3451.3, 3445.1, 1.8, 3475.0, 3380.0, 95.6, "1:2.0"),
            ("SOLUSDT", "LONG", 121.8, 121.0, 50, 118.5, 125.8, -40.8, "1:1.5"),
        ]
        self.setRowCount(len(sample))
        for row, (symbol, direction, entry, current, size, sl, tp, pnl, ratio) in enumerate(sample):
            direction_item = QtWidgets.QTableWidgetItem(direction)
            pnl_item = QtWidgets.QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if pnl >= 0 else QtGui.QColor("#F6465D"))

            direction_item.setForeground(QtGui.QColor("#0ECB81") if direction == "LONG" else QtGui.QColor("#F6465D"))

            self.setItem(row, 0, QtWidgets.QTableWidgetItem(symbol))
            self.setItem(row, 1, direction_item)
            self.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{entry:,.2f}"))
            self.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{current:,.2f}"))
            self.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{size:,.2f}"))
            self.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{sl:,.2f}"))
            self.setItem(row, 6, QtWidgets.QTableWidgetItem(f"{tp:,.2f}"))
            self.setItem(row, 7, pnl_item)
            self.setItem(row, 8, QtWidgets.QTableWidgetItem(ratio))
        self.setSortingEnabled(True)


class HistoryWidget(MockTable):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 6, parent)
        self.setHorizontalHeaderLabels(["Время", "Пара", "Направление", "Вход", "Выход", "PNL"])
        # Don't populate mock data - wait for real data from bot
        self.setSortingEnabled(True)

    def populate_mock_data(self):
        self.setSortingEnabled(False)
        now = datetime.now()
        data = []
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "NEARUSDT"]
        for i in range(12):
            symbol = random.choice(symbols)
            direction = random.choice(["LONG", "SHORT"])
            entry = round(1000 + (hash(symbol) % 1000) + random.uniform(-25, 25), 2)
            exit_price = entry + random.uniform(-15, 18)
            pnl = round((exit_price - entry) * random.uniform(0.5, 3.0), 2)
            if direction == "SHORT":
                pnl *= -1
            data.append((now - timedelta(minutes=i * 5), symbol, direction, entry, exit_price, pnl))
        self.setRowCount(len(data))
        for row, (ts, symbol, direction, entry, exit_price, pnl) in enumerate(data):
            self.setItem(row, 0, QtWidgets.QTableWidgetItem(ts.strftime("%d.%m %H:%M")))
            self.setItem(row, 1, QtWidgets.QTableWidgetItem(symbol))
            direction_item = QtWidgets.QTableWidgetItem(direction)
            direction_item.setForeground(QtGui.QColor("#0ECB81") if direction == "LONG" else QtGui.QColor("#F6465D"))
            self.setItem(row, 2, direction_item)
            self.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{entry:,.2f}"))
            self.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{exit_price:,.2f}"))
            pnl_item = QtWidgets.QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if pnl >= 0 else QtGui.QColor("#F6465D"))
            self.setItem(row, 5, pnl_item)
        self.setSortingEnabled(True)


class TradingPrototype(QtWidgets.QMainWindow):
    # Signals for thread-safe updates
    update_account_signal = QtCore.Signal(float, float, float, float, int)
    update_signals_signal = QtCore.Signal(dict)
    update_positions_signal = QtCore.Signal(dict, dict)
    update_history_signal = QtCore.Signal(list)
    
    def __init__(self):
        super().__init__()

        self.setObjectName("ScalpingPrototype")
        self.setWindowTitle("Scalping Bot – Qt Prototype")
        self.resize(1366, 700)
        
        # Connect internal signals
        self.update_account_signal.connect(self.update_account_data)
        self.update_signals_signal.connect(self.update_signals_data)
        self.update_positions_signal.connect(self.update_positions_data)
        self.update_history_signal.connect(self.update_history_data)
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AnimatedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
        )

        # Apply Binance-like stylesheet
        self._apply_styles()

        # Central widget with control panel
        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(12)

        self.control_panel = ControlPanel()
        central_layout.addWidget(self.control_panel)

        self.signals_widget = SignalsWidget()
        self.signals_widget.cellClicked.connect(self._on_signal_selected)
        self._active_signal_symbol = None

        workspace = self._build_workspace_section()
        central_layout.addWidget(workspace, 1)

        self.setCentralWidget(central)

        self._select_initial_signal()

        # Status bar
        status = self.statusBar()
        status.setObjectName("StatusBar")
        status.showMessage("No connection • Mock mode")

        self.control_panel.connectionToggled.connect(self._on_connection_toggle)
        self.control_panel.autoTradingToggled.connect(self._on_auto_trading_toggle)
        self.control_panel.refreshRequested.connect(self._on_refresh_requested)

        self._connection_active = True
        self._auto_trading_active = False

        # Initialize with zero data (will be updated by bot)
        self.control_panel.set_connection_toggle_state(False, silent=True)
        self.control_panel.set_auto_trading_state(False, silent=True)
        self.control_panel.update_balance(0)
        self.control_panel.update_pnl(0)
        self.control_panel.update_winrate(0)
        self.control_panel.update_risk_metrics(0, 0, 0)
        
        self._apply_signal_filters()
        self._update_signal_quality()
        self.statusBar().showMessage("Ожидание подключения...")

    def _build_workspace_section(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        container.setObjectName("WorkspaceFrame")
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(12, 6, 12, 12)
        container_layout.setSpacing(8)

        self.positions_widget = PositionsWidget()
        self.history_widget = HistoryWidget()

        left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        left_splitter.setObjectName("ContentSplitter")
        left_splitter.setChildrenCollapsible(False)

        signals_frame = self._section_frame("Signal Scanner", self._build_signals_panel())
        signals_frame.setMinimumHeight(200)
        left_splitter.addWidget(signals_frame)

        positions_frame = self._section_frame("Open Positions", self.positions_widget)
        positions_frame.setMinimumHeight(180)
        positions_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_splitter.addWidget(positions_frame)

        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 3)
        left_splitter.setSizes([220, 280])

        history_frame = self._section_frame("Trade History", self.history_widget)
        history_frame.setMinimumWidth(350)
        history_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        main_splitter.setObjectName("ContentSplitter")
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(history_frame)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([850, 450])

        container_layout.addWidget(main_splitter)

        self._update_signal_stats()

        return container

    def _build_signals_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(6)

        # === ROW 1: Filters + Search + Counter ===
        row1_layout = QtWidgets.QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(8)

        # Filter chips
        self.signal_filter_buttons: list[QtWidgets.QToolButton] = []
        for label in ("LONG", "SHORT", "WAIT"):
            button = self._create_filter_chip(label)
            self.signal_filter_buttons.append(button)
            row1_layout.addWidget(button)

        self.signal_reset_button = QtWidgets.QToolButton()
        self.signal_reset_button.setObjectName("GhostLink")
        self.signal_reset_button.setText("Сброс")
        self.signal_reset_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.signal_reset_button.clicked.connect(self._reset_signal_filters)
        row1_layout.addWidget(self.signal_reset_button)

        row1_layout.addStretch()

        # Search
        self.signal_search = QtWidgets.QLineEdit()
        self.signal_search.setObjectName("SearchField")
        self.signal_search.setPlaceholderText("Поиск пары...")
        self.signal_search.setClearButtonEnabled(True)
        self.signal_search.setFixedWidth(180)
        self.signal_search.textChanged.connect(self._apply_signal_filters)
        row1_layout.addWidget(self.signal_search)

        # Counter
        self.signal_filter_summary = QtWidgets.QLabel("6 из 6")
        self.signal_filter_summary.setObjectName("FilterSummary")
        self.signal_filter_summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.signal_filter_summary.setMinimumWidth(60)
        row1_layout.addWidget(self.signal_filter_summary)

        panel_layout.addLayout(row1_layout)

        # === ROW 2: Summary + Quick Actions ===
        row2_layout = QtWidgets.QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(16)

        # Summary labels (compact inline)
        self.avg_confidence_label = QtWidgets.QLabel("Ср. уверенность: 61%")
        self.avg_confidence_label.setObjectName("SummaryText")
        row2_layout.addWidget(self.avg_confidence_label)

        self.rejected_today_label = QtWidgets.QLabel("Отклонено сегодня: 15")
        self.rejected_today_label.setObjectName("SummaryText")
        row2_layout.addWidget(self.rejected_today_label)

        row2_layout.addStretch()

        # Quick action buttons
        self.close_all_button = QtWidgets.QPushButton("Закрыть все")
        self.close_all_button.setObjectName("DangerButton")
        self.close_all_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.close_all_button.setMinimumHeight(26)
        self.close_all_button.setFixedWidth(100)
        row2_layout.addWidget(self.close_all_button)

        self.pause_button = QtWidgets.QPushButton("Пауза")
        self.pause_button.setObjectName("SecondaryButton")
        self.pause_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.pause_button.setCheckable(True)
        self.pause_button.setMinimumHeight(26)
        self.pause_button.setFixedWidth(80)
        row2_layout.addWidget(self.pause_button)

        panel_layout.addLayout(row2_layout)

        # Table
        panel_layout.addWidget(self.signals_widget)

        return panel

    def _create_filter_chip(self, label: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(label)
        button.setObjectName("FilterChip")
        button.setCheckable(True)
        button.setChecked(True)
        button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        button.setToolTip(f"Show {label} signals")
        button.toggled.connect(self._apply_signal_filters)
        return button

    def _section_frame(self, title: str, content: QtWidgets.QWidget) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("SectionFrame")
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(4)
        header = QtWidgets.QLabel(title.upper())
        header.setObjectName("SectionTitle")
        v.addWidget(header)
        v.addWidget(content)
        return frame

    def _select_initial_signal(self) -> None:
        if self.signals_widget.rowCount() == 0:
            return
        self.signals_widget.selectRow(0)
        symbol = self.signals_widget.get_symbol(0)
        if symbol:
            self._set_active_signal(symbol)

    def _on_signal_selected(self, row: int, _column: int) -> None:
        symbol = self.signals_widget.get_symbol(row)
        if symbol:
            self._set_active_signal(symbol)

    def _set_active_signal(self, symbol: str) -> None:
        if not symbol or symbol == "—":
            self.signals_widget.clearSelection()
            if self._active_signal_symbol is not None:
                self.statusBar().showMessage("Нет сигналов после фильтра • Моковый режим", 3000)
            self._active_signal_symbol = None
            return
        self.signals_widget.highlight_symbol(symbol)
        if symbol != self._active_signal_symbol:
            self.statusBar().showMessage(f"Активный сигнал: {symbol} • Моковый режим")
        self._active_signal_symbol = symbol

    def _update_signal_stats(self) -> None:
        # Update positions count
        positions_count = self.positions_widget.rowCount()
        margin_used = 35.0  # Mock
        drawdown = 2.4  # Mock
        self.control_panel.update_risk_metrics(margin_used, drawdown, positions_count)
    
    def _update_signal_quality(self) -> None:
        """Update signal quality summary"""
        confidences = []
        
        for row in range(self.signals_widget.rowCount()):
            if self.signals_widget.isRowHidden(row):
                continue
            conf_item = self.signals_widget.item(row, 2)
            if conf_item:
                try:
                    conf_str = conf_item.text().replace('%', '')
                    conf_val = float(conf_str)
                    confidences.append(conf_val)
                except ValueError:
                    pass
        
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        self.avg_confidence_label.setText(f"Ср. уверенность: {avg_conf:.0f}%")
        self.rejected_today_label.setText("Отклонено сегодня: 15")  # Mock data

    @QtCore.Slot(bool)
    def _on_connection_toggle(self, connected: bool) -> None:
        self._connection_active = connected
        if connected:
            self.statusBar().showMessage("Подключение установлено • Моковый режим", 3000)
        else:
            self.statusBar().showMessage("Соединение закрыто • Моковый режим", 3000)

    @QtCore.Slot(bool)
    def _on_auto_trading_toggle(self, active: bool) -> None:
        self._auto_trading_active = active
        message = "Автоторговля запущена • Моковый режим" if active else "Автоторговля остановлена • Моковый режим"
        self.statusBar().showMessage(message, 3000)

    @QtCore.Slot()
    def _on_refresh_requested(self) -> None:
        # Refresh will be handled by bot calling update methods
        self._apply_signal_filters()
        self.statusBar().showMessage("Данные обновляются...", 2000)

    def _apply_signal_filters(self) -> None:
        if not hasattr(self, "signal_filter_buttons"):
            return
        directions = {button.text().upper() for button in self.signal_filter_buttons if button.isChecked()}
        search_text = self.signal_search.text() if hasattr(self, "signal_search") else ""
        self.signals_widget.filter_rows(search_text, directions)
        self._update_signal_filter_summary()
        self._update_signal_stats()
        self._update_signal_quality()
        self._ensure_visible_signal_selection()

    @QtCore.Slot()
    def _reset_signal_filters(self) -> None:
        if not hasattr(self, "signal_filter_buttons"):
            return
        for button in self.signal_filter_buttons:
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)
        if hasattr(self, "signal_search"):
            self.signal_search.blockSignals(True)
            self.signal_search.clear()
            self.signal_search.blockSignals(False)
        self._apply_signal_filters()

    def _update_signal_filter_summary(self) -> None:
        if not hasattr(self, "signal_filter_summary"):
            return
        total = self.signals_widget.rowCount()
        visible = self.signals_widget.visible_row_count()
        self.signal_filter_summary.setText(f"{visible} из {total}")

    def _ensure_visible_signal_selection(self) -> None:
        current_row = self.signals_widget.currentRow()
        if current_row >= 0 and not self.signals_widget.isRowHidden(current_row):
            symbol = self.signals_widget.get_symbol(current_row)
            if symbol:
                self._set_active_signal(symbol)
            return
        next_row = self.signals_widget.first_visible_row()
        if next_row is None:
            self._set_active_signal("—")
            return
        self.signals_widget.blockSignals(True)
        self.signals_widget.selectRow(next_row)
        self.signals_widget.blockSignals(False)
        symbol = self.signals_widget.get_symbol(next_row)
        if symbol:
            self._set_active_signal(symbol)

    def _apply_styles(self):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#0B0E11"))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#EAECEF"))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#14151A"))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#161A1F"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#0B0E11"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#EAECEF"))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#EAECEF"))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#14151A"))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#EAECEF"))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#F0B90B"))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#0B0E11"))
        self.setPalette(palette)

        self.setStyleSheet("""
            QMainWindow#ScalpingPrototype, QMainWindow {
                background-color: #0B0E11;
            }
            QLabel {
                color: #EAECEF;
            }
            QLabel#MetricTitle {
                color: #8B949E;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QLabel#MetricValue {
                color: #F0B90B;
                font-size: 16px;
                font-weight: 600;
            }
            QLabel#MetricValue[accentRole="positive"] { color: #0ECB81; }
            QLabel#MetricValue[accentRole="negative"] { color: #F6465D; }
            QLabel#MetricValue[accentRole="muted"] { color: #8B949E; }
            QWidget#Metric {
                background-color: #14151A;
                border-radius: 6px;
            }
            QWidget#WorkspaceFrame {
                background-color: #0B0E11;
            }
            QLabel#WorkspaceTitle {
                font-size: 14px;
                font-weight: 600;
                color: #F0F4F9;
                letter-spacing: 1px;
            }
            QLabel#WorkspaceHint {
                color: #6C727F;
                font-size: 12px;
            }
            QFrame#InfoCard {
                background-color: #14151A;
                border-radius: 10px;
                border: 1px solid rgba(240, 185, 11, 0.08);
            }
            QFrame#InfoCard QLabel#CardTitle {
                color: #7E8794;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QFrame#InfoCard QLabel#CardValue {
                color: #F0F4F9;
                font-size: 18px;
                font-weight: 600;
            }
            QFrame#SectionFrame {
                background-color: #14151A;
                border-radius: 10px;
                border: 1px solid rgba(31, 35, 43, 0.9);
            }
            QFrame#SectionFrame QLabel#SectionTitle {
                color: #7E8794;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QFrame#StatChip {
                background-color: #14151A;
                border-radius: 10px;
                border: 1px solid rgba(240, 185, 11, 0.18);
            }
            QFrame#StatChip QLabel#StatTitle {
                color: #7E8794;
                font-size: 8px;
                letter-spacing: 1.2px;
            }
            QFrame#StatChip QLabel#StatValue {
                color: #F0F4F9;
                font-size: 14px;
                font-weight: 600;
            }
            QFrame#StatusBadge {
                background-color: #151820;
                border-radius: 12px;
                border: 1px solid rgba(240, 185, 11, 0.18);
            }
            QLabel#StatusDot {
                background-color: #F6465D;
                border-radius: 5px;
            }
            QLabel#StatusDot[state="ok"] { background-color: #0ECB81; }
            QLabel#StatusDot[state="pending"] { background-color: #F0B90B; }
            QLabel#StatusDot[state="error"] { background-color: #F6465D; }
            QLabel#StatusText {
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QLabel#StatusText[accentRole="positive"] { color: #0ECB81; }
            QLabel#StatusText[accentRole="negative"] { color: #F6465D; }
            QLabel#StatusText[accentRole="accent"] { color: #F0B90B; }
            QLabel#ModeChip {
                background-color: rgba(240, 185, 11, 0.16);
                border-radius: 8px;
                padding: 2px 10px;
                font-size: 10px;
                letter-spacing: 1px;
                color: #F0B90B;
            }
            QLabel#ModeChip[accentRole="positive"] {
                background-color: rgba(14, 203, 129, 0.2);
                color: #0ECB81;
            }
            QLabel#ModeChip[accentRole="negative"] {
                background-color: rgba(246, 70, 93, 0.2);
                color: #F6465D;
            }
            QGroupBox#ControlCard {
                background-color: #151820;
                border: 1px solid rgba(240, 185, 11, 0.18);
                border-radius: 10px;
                font-size: 11px;
                color: #A2A9B4;
            }
            QGroupBox#ControlCard:title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                margin-left: 8px;
                color: #F0F4F9;
                font-weight: 600;
                letter-spacing: 0.6px;
            }
            QLabel#SliderValue {
                color: #F0B90B;
                font-size: 14px;
                font-weight: 600;
                padding-left: 8px;
            }
            QLabel#ControlCaption {
                color: #EAECEF;
                font-weight: 600;
                font-size: 13px;
            }
            QWidget#ControlPanel {
                background-color: #0B0E11;
            }
            QSlider::groove:horizontal {
                border: 1px solid rgba(240, 185, 11, 0.45);
                height: 10px;
                margin: 6px 0;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #1E272F, stop:1 #2B3540);
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 rgba(240, 185, 11, 0.9),
                                            stop:1 rgba(240, 185, 11, 0.2));
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #F0B90B;
                border: none;
                width: 22px;
                margin: -8px 0;
                border-radius: 11px;
                box-shadow: 0 0 10px rgba(240, 185, 11, 0.55);
            }
            QComboBox, QComboBox QAbstractItemView {
                background-color: #14151A;
                color: #EAECEF;
                border: 1px solid #232832;
                padding: 4px 8px;
                selection-background-color: #F0B90B;
                selection-color: #0B0E11;
            }
            QPushButton {
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                letter-spacing: 0.4px;
                background-color: #1B1F27;
                border: 1px solid #232832;
                color: #EAECEF;
            }
            QPushButton:hover {
                background-color: #232A34;
            }
            QPushButton#PrimaryButton {
                background-color: rgba(240, 185, 11, 0.12);
                border: 1px solid rgba(240, 185, 11, 0.45);
                color: #F0B90B;
            }
            QPushButton#PrimaryButton[active="true"] {
                background-color: rgba(14, 203, 129, 0.26);
                border-color: rgba(14, 203, 129, 0.62);
                color: #0ECB81;
            }
            QPushButton#SecondaryButton {
                background-color: rgba(240, 185, 11, 0.08);
                border: 1px solid rgba(240, 185, 11, 0.4);
                color: #F0F4F9;
            }
            QPushButton#SecondaryButton[active="true"] {
                background-color: rgba(240, 185, 11, 0.25);
                color: #0B0E11;
            }
            QPushButton#GhostButton {
                background-color: transparent;
                border: 1px solid rgba(234, 236, 239, 0.08);
                color: #A2A9B4;
            }
            QPushButton#GhostButton:hover {
                border-color: rgba(240, 185, 11, 0.45);
                color: #F0F4F9;
            }
            QPushButton#DangerButton {
                background-color: rgba(246, 70, 93, 0.12);
                border: 1px solid rgba(246, 70, 93, 0.45);
                color: #F6465D;
            }
            QPushButton#DangerButton:hover {
                background-color: rgba(246, 70, 93, 0.25);
                border-color: rgba(246, 70, 93, 0.65);
            }
            QLineEdit#SearchField {
                background-color: #12141C;
                border: 1px solid rgba(240, 185, 11, 0.16);
                border-radius: 8px;
                padding: 6px 12px;
                color: #EAECEF;
            }
            QLineEdit#SearchField::placeholder {
                color: #5C6470;
            }
            QLineEdit#SearchField:focus {
                border-color: rgba(240, 185, 11, 0.45);
                box-shadow: 0 0 0 1px rgba(240, 185, 11, 0.18);
            }
            QLabel#FilterSummary {
                color: #7E8794;
                font-size: 11px;
            }
            QToolButton#FilterChip {
                border-radius: 12px;
                border: 1px solid rgba(234, 236, 239, 0.12);
                padding: 4px 14px;
                color: #9AA1AC;
                background-color: rgba(20, 24, 31, 0.75);
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QToolButton#FilterChip:hover {
                border-color: rgba(240, 185, 11, 0.45);
                color: #F0F4F9;
            }
            QToolButton#FilterChip:checked {
                background-color: rgba(240, 185, 11, 0.24);
                border-color: rgba(240, 185, 11, 0.6);
                color: #F0B90B;
            }
            QToolButton#GhostLink {
                border: none;
                color: #7E8794;
                padding: 4px 8px;
                font-size: 11px;
            }
            QToolButton#GhostLink:hover {
                color: #F0F4F9;
            }
            QComboBox#RiskCombo {
                border: 1px solid rgba(240, 185, 11, 0.45);
                background-color: #202833;
                font-weight: 600;
                padding: 6px 10px;
                color: #F0F4F9;
                border-radius: 8px;
                min-width: 120px;
            }
            QComboBox#RiskCombo::drop-down {
                width: 24px;
                border: none;
            }
            QComboBox#RiskCombo QAbstractItemView {
                background-color: #1B1F27;
                border: 1px solid rgba(240, 185, 11, 0.4);
                padding: 6px;
            }
            QTableView#DataTable {
                background-color: #14151A;
                alternate-background-color: rgba(255,255,255,0.02);
                color: #EAECEF;
                gridline-color: rgba(255,255,255,0.05);
                border: none;
            }
            QHeaderView#TableHeader::section {
                background-color: #13161B;
                color: #7E8794;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #1F232B;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QStatusBar#StatusBar {
                background-color: #0B0E11;
                color: #6C727F;
                border-top: 1px solid #1F232B;
            }
            QTextEdit {
                background-color: #14151A;
                border: 1px solid #23262F;
                color: #EAECEF;
            }
            QSplitter#ContentSplitter::handle {
                background-color: #0D1016;
                width: 6px;
                margin: 8px 0;
            }
            QSplitter#ContentSplitter::handle:pressed {
                background-color: rgba(240, 185, 11, 0.4);
            }
            QLabel#SummaryText {
                color: #848E9C;
                font-size: 12px;
                font-weight: 500;
            }
        """)
    
    # ========== DATA UPDATE METHODS ==========
    
    def update_account_data(self, balance: float, pnl: float, winrate: float, drawdown: float, positions_count: int):
        """Update account metrics in control panel."""
        self.control_panel.update_balance(balance)
        self.control_panel.update_pnl(pnl)
        self.control_panel.update_winrate(winrate)
        
        # Calculate margin used (mock for now)
        margin_used = (positions_count / 10) * 100  # Assuming max 10 positions
        self.control_panel.update_risk_metrics(margin_used, drawdown, positions_count)
    
    def update_signals_data(self, signals: dict):
        """Update signals table."""
        self.signals_widget.setSortingEnabled(False)
        self.signals_widget.setRowCount(0)
        
        if not signals:
            self.signals_widget.setSortingEnabled(True)
            self._update_signal_quality()
            return
        
        self.signals_widget.setRowCount(len(signals))
        for row, (symbol, signal_obj) in enumerate(signals.items()):
            # Column 0: Symbol
            self.signals_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(symbol))
            
            # Column 1: Direction (signal_obj is TradingSignal object)
            direction = signal_obj.direction if hasattr(signal_obj, 'direction') else 'WAIT'
            direction_item = QtWidgets.QTableWidgetItem(direction)
            if direction == "LONG":
                direction_item.setForeground(QtGui.QColor("#0ECB81"))
            elif direction == "SHORT":
                direction_item.setForeground(QtGui.QColor("#F6465D"))
            self.signals_widget.setItem(row, 1, direction_item)
            
            # Column 2: Confidence
            confidence = signal_obj.confidence if hasattr(signal_obj, 'confidence') else 0
            self.signals_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{confidence:.0f}%"))
            
            # Column 3: Comment
            reasons = signal_obj.reasons if hasattr(signal_obj, 'reasons') else []
            comment = ', '.join(reasons[:2]) if reasons else ''  # First 2 reasons
            self.signals_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(comment))
        
        self.signals_widget.setSortingEnabled(True)
        self._update_signal_quality()
    
    def update_positions_data(self, positions: dict, current_prices: dict):
        """Update positions table."""
        self.positions_widget.setSortingEnabled(False)
        self.positions_widget.setRowCount(0)
        
        if not positions:
            self.positions_widget.setSortingEnabled(True)
            return
        
        self.positions_widget.setRowCount(len(positions))
        for row, (symbol, pos) in enumerate(positions.items()):
            current_price = current_prices.get(symbol, 0)
            
            # Calculate PNL
            if pos['side'] == 'LONG':
                pnl = (current_price - pos['entry_price']) * pos['size']
            else:
                pnl = (pos['entry_price'] - current_price) * pos['size']
            
            # Calculate R:R
            risk = abs(pos['entry_price'] - pos.get('stop_loss', pos['entry_price']))
            reward = abs(pos.get('take_profit', pos['entry_price']) - pos['entry_price'])
            rr_ratio = f"1:{reward/risk:.1f}" if risk > 0 else "1:0"
            
            # Column 0: Symbol
            self.positions_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(symbol))
            
            # Column 1: Direction
            direction_item = QtWidgets.QTableWidgetItem(pos['side'])
            direction_item.setForeground(
                QtGui.QColor("#0ECB81") if pos['side'] == 'LONG' else QtGui.QColor("#F6465D")
            )
            self.positions_widget.setItem(row, 1, direction_item)
            
            # Column 2-8: Entry, Current, Size, SL, TP, PNL, R:R
            self.positions_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{pos['entry_price']:,.2f}"))
            self.positions_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{current_price:,.2f}"))
            self.positions_widget.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{pos['size']:,.2f}"))
            self.positions_widget.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{pos.get('stop_loss', 0):,.2f}"))
            self.positions_widget.setItem(row, 6, QtWidgets.QTableWidgetItem(f"{pos.get('take_profit', 0):,.2f}"))
            
            pnl_item = QtWidgets.QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if pnl >= 0 else QtGui.QColor("#F6465D"))
            self.positions_widget.setItem(row, 7, pnl_item)
            
            self.positions_widget.setItem(row, 8, QtWidgets.QTableWidgetItem(rr_ratio))
        
        self.positions_widget.setSortingEnabled(True)
    
    def update_history_data(self, closed_trades: list):
        """Update history table."""
        self.history_widget.setSortingEnabled(False)
        self.history_widget.setRowCount(0)
        
        if not closed_trades:
            self.history_widget.setSortingEnabled(True)
            return
        
        # Show last 50 trades
        recent_trades = closed_trades[-50:] if len(closed_trades) > 50 else closed_trades
        self.history_widget.setRowCount(len(recent_trades))
        
        for row, trade in enumerate(reversed(recent_trades)):
            # Column 0: Time
            close_time = trade.get('close_time', datetime.now())
            time_str = close_time.strftime("%d.%m %H:%M") if isinstance(close_time, datetime) else str(close_time)
            self.history_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(time_str))
            
            # Column 1: Symbol
            self.history_widget.setItem(row, 1, QtWidgets.QTableWidgetItem(trade.get('symbol', '')))
            
            # Column 2: Direction
            direction = trade.get('side', '')
            direction_item = QtWidgets.QTableWidgetItem(direction)
            direction_item.setForeground(
                QtGui.QColor("#0ECB81") if direction == 'LONG' else QtGui.QColor("#F6465D")
            )
            self.history_widget.setItem(row, 2, direction_item)
            
            # Column 3-5: Entry, Exit, PNL
            self.history_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{trade.get('entry_price', 0):,.2f}"))
            self.history_widget.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{trade.get('exit_price', 0):,.2f}"))
            
            pnl = trade.get('pnl', 0)
            pnl_item = QtWidgets.QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if pnl >= 0 else QtGui.QColor("#F6465D"))
            self.history_widget.setItem(row, 5, pnl_item)
        
        self.history_widget.setSortingEnabled(True)


def main():
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Scalping Bot – Design Prototype")
    app.setStyle("Fusion")

    window = TradingPrototype()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

