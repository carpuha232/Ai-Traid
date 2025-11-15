#!/usr/bin/env python3
"""
PySide6 prototype for a Binance-style trading terminal.
This UI is disconnected from the actual bot logic and serves purely as a design playground.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from PySide6 import QtCore, QtGui, QtWidgets
from typing import List, Optional


# Import widgets from modular components
from .widgets import (
    ControlPanel,
    ActivityLogWidget,
    SignalsWidget,
    PositionsWidget,
    HistoryWidget,
    OrdersWidget,
)



class TradingPrototype(QtWidgets.QMainWindow):
    # Signals for thread-safe updates
    update_account_signal = QtCore.Signal(float, float, float, float, float, int)
    update_signals_signal = QtCore.Signal(dict)
    update_positions_signal = QtCore.Signal(dict, dict)
    update_history_signal = QtCore.Signal(list)
    update_orders_signal = QtCore.Signal(list)
    start_position_requested = QtCore.Signal(str)
    
    def __init__(self, pairs: Optional[List[str]] = None):
        super().__init__()

        self.setObjectName("ScalpingPrototype")
        self.setWindowTitle("Scalping Bot – Qt Prototype")
        self.resize(1366, 700)
        self.available_pairs = pairs or []
        
        # Connect internal signals
        self.update_account_signal.connect(self.update_account_data)
        self.update_signals_signal.connect(self.update_signals_data)
        self.update_positions_signal.connect(self.update_positions_data)
        self.update_history_signal.connect(self.update_history_data)
        self.update_orders_signal.connect(self.update_orders_data)
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
        central_layout.setSpacing(0)  # No spacing between panels

        self.control_panel = ControlPanel()
        central_layout.addWidget(self.control_panel)

        self.activity_log = ActivityLogWidget()
        self._active_signal_symbol = None

        workspace = self._build_workspace_section()
        central_layout.addWidget(workspace, 1)

        self.setCentralWidget(central)

        # Status bar
        status = self.statusBar()
        status.setObjectName("StatusBar")
        status.showMessage("No connection • Mock mode")

        self.control_panel.connectionToggled.connect(self._on_connection_toggle)

        self._connection_active = True

        # Initialize with zero data (will be updated by bot)
        self.control_panel.set_connection_toggle_state(True, silent=True)  # Start as "connected"
        self.control_panel.update_balance(0)
        self.control_panel.update_pnl(0)
        self.control_panel.update_winrate(0)
        self.control_panel.update_risk_metrics(0, 0, 0)
        
        self.statusBar().showMessage("Ожидание подключения...")

    def _build_workspace_section(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        container.setObjectName("WorkspaceFrame")
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(12, 0, 12, 0)  # Remove top/bottom margins
        container_layout.setSpacing(8)

        self.positions_widget = PositionsWidget()
        self.orders_widget = OrdersWidget()
        self.history_widget = HistoryWidget()

        left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        left_splitter.setObjectName("ContentSplitter")
        left_splitter.setChildrenCollapsible(False)

        signals_frame = self._section_frame("Signal Scanner", self._build_signals_panel())
        signals_frame.setMinimumHeight(200)
        left_splitter.addWidget(signals_frame)

        positions_frame = self._build_positions_section()
        positions_frame.setMinimumHeight(180)
        positions_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_splitter.addWidget(positions_frame)

        orders_frame = self._section_frame("Open Orders", self.orders_widget)
        orders_frame.setMinimumHeight(140)
        orders_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_splitter.addWidget(orders_frame)

        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 3)
        left_splitter.setStretchFactor(2, 2)
        left_splitter.setSizes([200, 260, 200])

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
        # Just return activity log widget - no extra layout needed
        return self.activity_log

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

    def _build_positions_section(self) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("SectionFrame")
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(4)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QLabel("OPEN POSITIONS")
        header.setObjectName("SectionTitle")
        header_row.addWidget(header)
        header_row.addStretch(1)

        self.start_symbol_combo = QtWidgets.QComboBox()
        self.start_symbol_combo.setObjectName("StartSymbolCombo")
        self.start_symbol_combo.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.start_symbol_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        if self.available_pairs:
            self.start_symbol_combo.addItems(self.available_pairs)
        else:
            self.start_symbol_combo.addItem("XRPUSDT")
        header_row.addWidget(self.start_symbol_combo)

        self.start_button = QtWidgets.QPushButton("Старт")
        self.start_button.setObjectName("StartPositionButton")
        self.start_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.start_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.start_button.setMinimumWidth(90)
        self.start_button.clicked.connect(self._on_start_button_clicked)
        header_row.addWidget(self.start_button)

        v.addLayout(header_row)
        v.addWidget(self.positions_widget)
        return frame

    def _update_signal_stats(self) -> None:
        # Update positions count
        positions_count = self.positions_widget.rowCount()
        margin_used = 35.0  # Mock
        drawdown = 2.4  # Mock
        self.control_panel.update_risk_metrics(margin_used, drawdown, positions_count)
    
    @QtCore.Slot(bool)
    def _on_connection_toggle(self, connected: bool) -> None:
        self._connection_active = connected
        if connected:
            self.statusBar().showMessage("Подключение установлено • Моковый режим", 3000)
        else:
            self.statusBar().showMessage("Соединение закрыто • Моковый режим", 3000)

    @QtCore.Slot()
    def _on_start_button_clicked(self):
        """Emit event to открыть минимальную позицию."""
        symbol = ""
        if hasattr(self, "start_symbol_combo") and self.start_symbol_combo.count() > 0:
            symbol = self.start_symbol_combo.currentText()
        self.start_position_requested.emit(symbol)


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
            QPushButton#StartPositionButton {
                background-color: rgba(14, 203, 129, 0.18);
                border: 1px solid rgba(14, 203, 129, 0.45);
                color: #0ECB81;
                font-size: 11px;
                padding: 6px 12px;
            }
            QPushButton#StartPositionButton:hover {
                background-color: rgba(14, 203, 129, 0.32);
            }
            QPushButton#StartPositionButton:disabled {
                background-color: rgba(126, 135, 148, 0.2);
                border-color: rgba(126, 135, 148, 0.35);
                color: #7E8794;
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
    
    def _on_close_button_clicked(self):
        """Handle close button click - gets symbol from sender."""
        button = self.sender()
        if not button:
            return
        
        # Get symbol from button property
        symbol = button.property("symbol")
        if not symbol:
            return
        
        # Disable button immediately to prevent multiple clicks
        button.setEnabled(False)
        button.setText("...")
        
        # Emit signal to close position
        self.positions_widget.closePositionRequested.emit(symbol)
    
    def _handle_close_button(self, symbol: str):
        """Handle close button click - called directly from button."""
        self.positions_widget.closePositionRequested.emit(symbol)
    
    def update_account_data(self, balance: float, pnl: float, winrate: float, drawdown: float, margin_used: float, positions_count: int):
        """Update account metrics in control panel."""
        self.control_panel.update_balance(balance)
        self.control_panel.update_pnl(pnl)
        self.control_panel.update_winrate(winrate)
        self.control_panel.update_risk_metrics(margin_used, drawdown, positions_count)
    
    def update_signals_data(self, signals: dict):
        """Add signals to activity log (only if confidence > 50%)."""
        if not signals:
            return
        
        for symbol, signal_obj in signals.items():
            # Extract signal data
            confidence = signal_obj.confidence if hasattr(signal_obj, 'confidence') else 0
            direction = signal_obj.direction if hasattr(signal_obj, 'direction') else 'WAIT'
            reasons = signal_obj.reasons if hasattr(signal_obj, 'reasons') else []
            
            # Get additional data if available
            prob_up = getattr(signal_obj, 'prob_up', 0)
            prob_down = getattr(signal_obj, 'prob_down', 0)
            bull_strength = getattr(signal_obj, 'bullish_strength', 0)
            bear_strength = getattr(signal_obj, 'bearish_strength', 0)
            
            # Add to activity log (will filter if < 50%)
            self.activity_log.add_analysis(symbol, {
                'confidence': confidence,
                'direction': direction,
                'prob_up': prob_up,
                'prob_down': prob_down,
                'bull_strength': bull_strength,
                'bear_strength': bear_strength,
                'reasons': reasons
            })
    
    def update_positions_data(self, positions: dict, current_prices: dict):
        """Update positions table."""
        if not positions:
            self.positions_widget.setRowCount(0)
            return
        
        self.positions_widget.setRowCount(len(positions))
        
        for row, (symbol, pos) in enumerate(positions.items()):
            display_symbol = symbol.split('|')[0] if '|' in symbol else symbol
            side = getattr(pos, 'side', 'LONG')
            leverage = int(getattr(pos, 'leverage', 1) or 1)
            entry_price = float(getattr(pos, 'entry_price', 0.0))
            size_qty = float(getattr(pos, 'size', 0.0))
            live_price = float(current_prices.get(symbol, getattr(pos, 'mark_price', entry_price)))
            mark_price = live_price
            break_even = float(getattr(pos, 'break_even_price', entry_price))
            liquidation = float(getattr(pos, 'liquidation_price', 0.0))
            margin_ratio = float(getattr(pos, 'margin_ratio', 0.0))
            if margin_ratio < 1:
                margin_ratio *= 100.0
            margin_used = float(getattr(pos, 'margin_usdt', 0.0))
            if margin_used <= 0 and leverage:
                margin_used = (entry_price * size_qty) / leverage if leverage else 0.0
            notional = float(getattr(pos, 'position_value_usdt', entry_price * size_qty))
            if side == 'LONG':
                unrealized = (live_price - entry_price) * size_qty
            else:
                unrealized = (entry_price - live_price) * size_qty
            roi = (unrealized / margin_used * 100.0) if margin_used else 0.0
            
            symbol_item = QtWidgets.QTableWidgetItem(f"{display_symbol}\nБесср {leverage}x")
            symbol_item.setForeground(QtGui.QColor("#0ECB81") if side == 'LONG' else QtGui.QColor("#F6465D"))
            self.positions_widget.setItem(row, 0, symbol_item)
            
            volume_item = QtWidgets.QTableWidgetItem(f"{notional:,.4f} USDT")
            self.positions_widget.setItem(row, 1, volume_item)
            self.positions_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{entry_price:,.4f}"))
            self.positions_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{break_even:,.4f}"))
            self.positions_widget.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{mark_price:,.4f}"))
            liq_item = QtWidgets.QTableWidgetItem(f"{liquidation:,.4f}")
            liq_item.setForeground(QtGui.QColor("#F6465D"))
            self.positions_widget.setItem(row, 5, liq_item)
            margin_ratio_item = QtWidgets.QTableWidgetItem(f"{margin_ratio:.2f}%")
            self.positions_widget.setItem(row, 6, margin_ratio_item)
            self.positions_widget.setItem(row, 7, QtWidgets.QTableWidgetItem(f"{margin_used:,.4f} USDT"))
            
            pnl_item = QtWidgets.QTableWidgetItem(f"{unrealized:+.4f} USDT ({roi:+.2f}%)")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if unrealized >= 0 else QtGui.QColor("#F6465D"))
            self.positions_widget.setItem(row, 8, pnl_item)
            
            existing_widget = self.positions_widget.cellWidget(row, 9)
            if existing_widget is None:
                container = QtWidgets.QWidget()
                container_layout = QtWidgets.QHBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                
                close_btn = QtWidgets.QPushButton("Закрыть")
                close_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
                close_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
                close_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(246, 70, 93, 0.12);
                        color: #F6465D;
                        border: 1px solid rgba(246, 70, 93, 0.35);
                        border-radius: 3px;
                        font-size: 9px;
                        font-weight: 600;
                        padding: 2px 6px;
                        min-width: 40px;
                        max-width: 50px;
                        min-height: 16px;
                        max-height: 16px;
                    }
                    QPushButton:hover {
                        background-color: rgba(246, 70, 93, 0.22);
                        border-color: rgba(246, 70, 93, 0.55);
                    }
                    QPushButton:pressed {
                        background-color: rgba(246, 70, 93, 0.32);
                    }
                    QPushButton:disabled {
                        background-color: rgba(107, 114, 128, 0.12);
                        color: #8B949E;
                        border-color: rgba(107, 114, 128, 0.25);
                    }
                """)
                close_btn.setProperty("symbol", symbol)
                close_btn.clicked.connect(self._on_close_button_clicked)
                
                container_layout.addWidget(close_btn)
                self.positions_widget.setCellWidget(row, 9, container)
            else:
                close_btn = existing_widget.findChild(QtWidgets.QPushButton)
                if close_btn:
                    close_btn.setProperty("symbol", symbol)
                    close_btn.setEnabled(True)
                    close_btn.setText("Закрыть")
    
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
            symbol = trade.symbol if hasattr(trade, 'symbol') else ''
            self.history_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(symbol))
            
            direction = trade.side if hasattr(trade, 'side') else ''
            direction_item = QtWidgets.QTableWidgetItem(direction)
            direction_item.setForeground(
                QtGui.QColor("#0ECB81") if direction == 'LONG' else QtGui.QColor("#F6465D")
            )
            self.history_widget.setItem(row, 1, direction_item)
            
            entry_price = trade.entry_price if hasattr(trade, 'entry_price') else 0
            exit_price = trade.exit_price if hasattr(trade, 'exit_price') else 0
            self.history_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{entry_price:,.4f}"))
            self.history_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{exit_price:,.4f}"))
            
            pnl = trade.pnl if hasattr(trade, 'pnl') else 0
            pnl_item = QtWidgets.QTableWidgetItem(f"{pnl:+.4f}")
            pnl_item.setForeground(QtGui.QColor("#0ECB81") if pnl >= 0 else QtGui.QColor("#F6465D"))
            self.history_widget.setItem(row, 4, pnl_item)
        
        self.history_widget.setSortingEnabled(True)

    def update_orders_data(self, orders: list):
        """Update open orders table."""
        self.orders_widget.setSortingEnabled(False)
        self.orders_widget.setRowCount(0)

        if not orders:
            self.orders_widget.setSortingEnabled(True)
            return

        self.orders_widget.setRowCount(len(orders))
        for row, order in enumerate(orders):
            symbol = order.get("symbol", "")
            side = order.get("side", "")
            order_type = order.get("type", "")
            price = float(order.get("price", 0.0) or 0.0)
            qty = float(order.get("origQty", 0.0) or 0.0)
            status = order.get("status", "")

            symbol_item = QtWidgets.QTableWidgetItem(symbol)
            side_item = QtWidgets.QTableWidgetItem(side)
            side_item.setForeground(
                QtGui.QColor("#0ECB81") if side.upper() == "BUY" else QtGui.QColor("#F6465D")
            )

            self.orders_widget.setItem(row, 0, symbol_item)
            self.orders_widget.setItem(row, 1, side_item)
            self.orders_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(order_type))
            self.orders_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{price:,.4f}"))
            self.orders_widget.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{qty:.4f}"))
            self.orders_widget.setItem(row, 5, QtWidgets.QTableWidgetItem(status))

        self.orders_widget.setSortingEnabled(True)

    @QtCore.Slot(bool, str)
    def set_start_button_state(self, enabled: bool, label: str = ""):
        """External control for Start button."""
        if hasattr(self, "start_button"):
            self.start_button.setEnabled(enabled)
            if label:
                self.start_button.setText(label)


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

