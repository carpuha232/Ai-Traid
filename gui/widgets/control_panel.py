#!/usr/bin/env python3
"""
Control Panel Widget - extracted from main_window.py
NO CHANGES - exact copy of lines 15-223
"""

from __future__ import annotations

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

        # === RIGHT: Trading control button ===
        self.connection_button = QtWidgets.QPushButton("Отключить")
        self.connection_button.setObjectName("PrimaryButton")
        self.connection_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.connection_button.setCheckable(True)
        self.connection_button.setMinimumHeight(36)
        self.connection_button.setFixedWidth(110)
        self.connection_button.setChecked(True)  # Start in "connected" state
        layout.addWidget(self.connection_button)

        # Wire signals
        self.connection_button.toggled.connect(self._on_connection_toggled)

        self._update_connection_button_text(True)  # Start as "connected"

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
        value_label.setText(f"${balance:,.2f}")

    def update_pnl(self, pnl: float) -> None:
        value_label = self.pnl_label.findChild(QtWidgets.QLabel, "MetricValue")
        sign = "+" if pnl >= 0 else ""
        value_label.setText(f"{sign}${pnl:,.2f}")
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

    def _on_connection_toggled(self, checked: bool) -> None:
        self._update_connection_button_text(checked)
        self.connectionToggled.emit(checked)

    def _update_connection_button_text(self, connected: bool) -> None:
        self.connection_button.setText("Отключить" if connected else "Подключить")
        self.connection_button.setProperty("active", "true" if connected else "false")
        self._refresh_widget(self.connection_button)

    @staticmethod
    def _refresh_widget(widget: QtWidgets.QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
