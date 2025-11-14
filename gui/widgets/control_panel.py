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
    singleOrderModeToggled = QtCore.Signal(bool)
    refreshRequested = QtCore.Signal()
    averagingDistanceChanged = QtCore.Signal(float)

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
        self.net_profit_label = self._metric_label("Чистая", "$0.00", "positive")
        self.winrate_label = self._metric_label("Винрейт", "62%", "accent")
        
        # Risk metrics
        self.margin_label = self._metric_label("Маржа", "35%", "muted")
        self.drawdown_label = self._metric_label("Просадка", "2.4%", "muted")
        self.positions_label = self._metric_label("Открыто", "4 поз.", "muted")

        metrics_layout.addWidget(self.balance_label)
        metrics_layout.addWidget(self.pnl_label)
        metrics_layout.addWidget(self.net_profit_label)
        metrics_layout.addWidget(self.winrate_label)
        metrics_layout.addSpacing(30)
        metrics_layout.addWidget(self.margin_label)
        metrics_layout.addWidget(self.drawdown_label)
        metrics_layout.addWidget(self.positions_label)
        metrics_layout.addStretch()

        layout.addLayout(metrics_layout)

        layout.addSpacing(20)

        # === RIGHT: Controls and buttons ===
        right_layout = QtWidgets.QHBoxLayout()
        right_layout.setSpacing(12)

        # Averaging distance slider container (отдельно, со своим процентом)
        self._averaging_slider_scale = 100  # 0.01% resolution
        self._averaging_slider_expand_step = 100  # expand by 1%
        self._averaging_signal_blocked = False
        self._pending_averaging_distance = 0.0

        averaging_layout = QtWidgets.QVBoxLayout()
        averaging_layout.setContentsMargins(0, 0, 0, 0)
        averaging_layout.setSpacing(2)

        averaging_caption = QtWidgets.QLabel("Усреднение от ликвидации")
        averaging_caption.setObjectName("ControlCaption")
        averaging_layout.addWidget(averaging_caption)

        averaging_controls = QtWidgets.QHBoxLayout()
        averaging_controls.setContentsMargins(0, 0, 0, 0)
        averaging_controls.setSpacing(6)

        self.averaging_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.averaging_slider.setMinimum(0)
        self.averaging_slider.setMaximum(200)  # initial 2.00%
        self.averaging_slider.setSingleStep(1)
        self.averaging_slider.setPageStep(5)
        self.averaging_slider.setFixedWidth(200)
        self.averaging_slider.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        averaging_controls.addWidget(self.averaging_slider)

        self.averaging_value_label = QtWidgets.QLabel("0.00%")
        self.averaging_value_label.setObjectName("SliderValue")
        self.averaging_value_label.setMinimumWidth(70)
        self.averaging_value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        averaging_controls.addWidget(self.averaging_value_label)

        averaging_layout.addLayout(averaging_controls)
        right_layout.addLayout(averaging_layout)

        # Отступ между ползунком и кнопками
        right_layout.addSpacing(16)

        # Кнопки: Подключить, Режим 1 ордера, Обновить
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.connection_button = QtWidgets.QPushButton("Подключить")
        self.connection_button.setObjectName("PrimaryButton")
        self.connection_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.connection_button.setCheckable(True)
        self.connection_button.setMinimumHeight(36)
        self.connection_button.setFixedWidth(110)
        buttons_layout.addWidget(self.connection_button)

        self.single_order_button = QtWidgets.QPushButton("ECO ВЫКЛ")
        self.single_order_button.setObjectName("PrimaryButton")  # Такой же стиль как "Подключить"
        self.single_order_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.single_order_button.setCheckable(True)
        self.single_order_button.setChecked(False)  # По умолчанию ВЫКЛ
        self.single_order_button.setMinimumHeight(36)
        self.single_order_button.setFixedWidth(110)  # Такая же ширина как "Подключить"
        buttons_layout.addWidget(self.single_order_button)

        self.refresh_button = QtWidgets.QPushButton("⟳")
        self.refresh_button.setObjectName("GhostButton")
        self.refresh_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setMinimumHeight(36)
        self.refresh_button.setFixedWidth(36)
        buttons_layout.addWidget(self.refresh_button)

        right_layout.addLayout(buttons_layout)
        layout.addLayout(right_layout)

        # Wire signals
        self.connection_button.toggled.connect(self._on_connection_toggled)
        self.single_order_button.toggled.connect(self._on_single_order_mode_toggled)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.averaging_slider.valueChanged.connect(self._on_averaging_slider_value_changed)

        self._averaging_emit_timer = QtCore.QTimer(self)
        self._averaging_emit_timer.setSingleShot(True)
        self._averaging_emit_timer.setInterval(400)
        self._averaging_emit_timer.timeout.connect(self._emit_averaging_distance)

        self._update_connection_button_text(False)
        self._update_single_order_button_text(False)
        self.set_averaging_distance(0.0, silent=True)

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
    
    def update_net_profit(self, net_profit: float) -> None:
        """Update net profit display (PNL - commissions)"""
        value_label = self.net_profit_label.findChild(QtWidgets.QLabel, "MetricValue")
        sign = "+" if net_profit >= 0 else ""
        value_label.setText(f"{sign}${net_profit:.2f}")
        value_label.setProperty("accentRole", "positive" if net_profit >= 0 else "negative")
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

    def set_single_order_mode_state(self, active: bool, silent: bool = False) -> None:
        """Установить состояние кнопки режима 1 ордера.
        
        Args:
            active: True = ВКЛ (режим 1 ордера), False = ВЫКЛ (обычный режим)
            silent: Если True, не эмитировать сигналы
        """
        if silent:
            self.single_order_button.blockSignals(True)
        # active=True -> checked=True -> "Режим 1 ордера ВКЛ"
        # active=False -> checked=False -> "Режим 1 ордера ВЫКЛ"
        self.single_order_button.setChecked(active)
        self._update_single_order_button_text(active)
        if silent:
            self.single_order_button.blockSignals(False)



    def _on_connection_toggled(self, checked: bool) -> None:
        self._update_connection_button_text(checked)
        self.connectionToggled.emit(checked)

    def _on_single_order_mode_toggled(self, checked: bool) -> None:
        """Обработка переключения кнопки режима 1 ордера.
        
        Args:
            checked: True = ВКЛ (режим 1 ордера), False = ВЫКЛ (обычный режим)
        """
        self._update_single_order_button_text(checked)
        # checked=True означает режим 1 ордера ВКЛ
        # checked=False означает обычный режим
        self.singleOrderModeToggled.emit(checked)

    def _on_refresh_clicked(self) -> None:
        self.refreshRequested.emit()

    def _update_connection_button_text(self, connected: bool) -> None:
        self.connection_button.setText("Отключить" if connected else "Подключить")
        self.connection_button.setProperty("active", "true" if connected else "false")
        self._refresh_widget(self.connection_button)

    def _update_single_order_button_text(self, checked: bool) -> None:
        """Обновление текста кнопки режима 1 ордера.
        
        Args:
            checked: True = ВКЛ (режим 1 ордера), False = ВЫКЛ (обычный режим)
        """
        # Используем короткий текст "ECO" чтобы поместился в 110px
        # checked=True -> "ECO ВКЛ"
        # checked=False -> "ECO ВЫКЛ"
        self.single_order_button.setText("ECO ВКЛ" if checked else "ECO ВЫКЛ")
        self.single_order_button.setProperty("active", "true" if checked else "false")
        self._refresh_widget(self.single_order_button)

    def _ensure_averaging_slider_range(self, distance: float) -> None:
        slider_value = int(round(distance * self._averaging_slider_scale))
        current_max = self.averaging_slider.maximum()
        if slider_value >= current_max:
            new_max = slider_value + self._averaging_slider_expand_step
            self.averaging_slider.setMaximum(new_max)

    def _update_averaging_display(self, distance: float) -> None:
        self.averaging_value_label.setText(f"{distance:.2f}%")

    @QtCore.Slot(int)
    def _on_averaging_slider_value_changed(self, raw_value: int) -> None:
        distance = max(0.0, raw_value / self._averaging_slider_scale)
        self._ensure_averaging_slider_range(distance)
        self._pending_averaging_distance = distance
        self._update_averaging_display(distance)
        if self._averaging_signal_blocked:
            return
        self._averaging_emit_timer.stop()
        self._averaging_emit_timer.start()

    def _emit_averaging_distance(self) -> None:
        if self._averaging_signal_blocked:
            return
        self.averagingDistanceChanged.emit(self._pending_averaging_distance)

    def set_averaging_distance(self, distance: float, silent: bool = False) -> None:
        distance = max(0.0, float(distance))
        self._ensure_averaging_slider_range(distance)
        slider_value = int(round(distance * self._averaging_slider_scale))

        self._averaging_emit_timer.stop()
        if silent:
            self._averaging_signal_blocked = True

        self.averaging_slider.blockSignals(True)
        self.averaging_slider.setValue(slider_value)
        self.averaging_slider.blockSignals(False)

        self._pending_averaging_distance = distance
        self._update_averaging_display(distance)

        if silent:
            self._averaging_signal_blocked = False

    @staticmethod
    def _refresh_widget(widget: QtWidgets.QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
