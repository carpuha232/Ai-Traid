#!/usr/bin/env python3
"""
Table Widgets - extracted from main_window.py
NO CHANGES - exact copy of lines 225-400
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from PySide6 import QtCore, QtGui, QtWidgets


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


class ActivityLogWidget(QtWidgets.QTextEdit):
    """Live activity log showing bot's 'thoughts' in real-time."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityLog")
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        
        # Styling
        self.setStyleSheet("""
            QTextEdit#ActivityLog {
                background-color: #0B0E11;
                color: #F0F4F9;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        
        # Auto-scroll enabled by default
        self.auto_scroll = True
        self.max_lines = 200  # Keep last 200 lines
        
        # Statistics
        self.total_scanned = 0
        self.signals_found = 0
        self.rejected_low_conf = 0
        self.rejected_liquidity = 0
    
    def add_analysis(self, symbol: str, data: dict):
        """Add analysis entry to log (only if confidence > 50%)."""
        confidence = data.get('confidence', 0)
        
        # Filter: only show if confidence > 50%
        if confidence < 50:
            self.rejected_low_conf += 1
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        direction = data.get('direction', 'WAIT')
        prob_up = data.get('prob_up', 0)
        prob_down = data.get('prob_down', 0)
        bull = data.get('bull_strength', 0)
        bear = data.get('bear_strength', 0)
        reasons = data.get('reasons', [])
        
        # Icon and color based on confidence
        if confidence >= 60:
            icon = "✅"
            color = "#0ECB81"  # Green
            status = f"{direction} сигнал {confidence:.1f}%"
        else:
            icon = "🔍"
            color = "#F0B90B"  # Yellow
            status = f"Уверенность {confidence:.1f}% < 60% → пропуск"
        
        # Format message
        html = f"""
        <div style='margin-bottom: 8px;'>
            <span style='color: #7E8794;'>{timestamp}</span>
            <span style='color: {color}; font-weight: bold;'> {icon} {symbol}:</span>
            <span style='color: #F0F4F9;'> {status}</span><br/>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Prob UP: {prob_up*100:.1f}% | Prob DOWN: {prob_down*100:.1f}%<br/>
            </span>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Bull: {bull} | Bear: {bear}<br/>
            </span>
        """
        
        # Add reasons if present
        if reasons:
            reasons_text = ', '.join(reasons[:3])  # First 3 reasons
            html += f"""
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • {reasons_text}<br/>
            </span>
            """
        
        html += "</div>"
        
        self.append(html)
        
        # Update stats
        if confidence >= 60:
            self.signals_found += 1
        
        # Auto-scroll
        if self.auto_scroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        # Limit lines
        self._trim_lines()
    
    def add_position_opened(self, symbol: str, data: dict):
        """Add position opened entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        side = data.get('side', 'LONG')
        entry = data.get('entry_price', 0)
        sl = data.get('stop_loss', 0)
        tp = data.get('take_profit', 0)
        risk = data.get('risk_percent', 0)
        leverage = data.get('leverage', 1)
        
        color = "#0ECB81" if side == "LONG" else "#F6465D"
        
        html = f"""
        <div style='margin-bottom: 8px;'>
            <span style='color: #7E8794;'>{timestamp}</span>
            <span style='color: #F0B90B; font-weight: bold;'> 💰 {symbol}:</span>
            <span style='color: {color};'> Позиция открыта {side}</span><br/>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Entry: {entry:,.2f} | SL: {sl:,.2f} | TP: {tp:,.2f}<br/>
            </span>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Risk: {risk:.1f}% | Leverage: {leverage}x<br/>
            </span>
        </div>
        """
        
        self.append(html)
        
        if self.auto_scroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        self._trim_lines()
    
    def add_position_closed(self, symbol: str, data: dict):
        """Add position closed entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        pnl = data.get('pnl', 0)
        pnl_percent = data.get('pnl_percent', 0)
        reason = data.get('reason', 'Manual close')
        
        color = "#0ECB81" if pnl >= 0 else "#F6465D"
        icon = "✅" if pnl >= 0 else "❌"
        
        html = f"""
        <div style='margin-bottom: 8px;'>
            <span style='color: #7E8794;'>{timestamp}</span>
            <span style='color: {color}; font-weight: bold;'> {icon} {symbol}:</span>
            <span style='color: {color};'> Позиция закрыта ({reason})</span><br/>
            <span style='color: {color}; margin-left: 20px; font-weight: bold;'>
                • PNL: {pnl:+.2f} USDT ({pnl_percent:+.2f}%)<br/>
            </span>
        </div>
        """
        
        self.append(html)
        
        if self.auto_scroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        self._trim_lines()
    
    def add_reject_liquidity(self, symbol: str, wall_score: float, spread_score: float):
        """Add liquidity rejection entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f"""
        <div style='margin-bottom: 8px;'>
            <span style='color: #7E8794;'>{timestamp}</span>
            <span style='color: #6C727F;'> ⏸️ {symbol}:</span>
            <span style='color: #8B949E;'> Пропуск</span><br/>
            <span style='color: #6C727F; margin-left: 20px;'>
                • Wall Score: {wall_score:.0f}/100 | Spread: {spread_score:.0f}/100<br/>
            </span>
            <span style='color: #6C727F; margin-left: 20px;'>
                ❌ Недостаточно ликвидности для входа<br/>
            </span>
        </div>
        """
        
        self.append(html)
        self.rejected_liquidity += 1
        
        if self.auto_scroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        self._trim_lines()
    
    def add_summary(self):
        """Add periodic summary."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f"""
        <div style='margin: 12px 0; padding: 8px; background-color: #14151A; border-left: 3px solid #F0B90B;'>
            <span style='color: #7E8794;'>{timestamp}</span>
            <span style='color: #F0B90B; font-weight: bold;'> 📊 Сводка за последние 30s:</span><br/>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Найдено сигналов (>50%): {self.signals_found}<br/>
            </span>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Отклонено (низкая уверенность): {self.rejected_low_conf}<br/>
            </span>
            <span style='color: #A2A9B4; margin-left: 20px;'>
                • Отклонено (ликвидность): {self.rejected_liquidity}<br/>
            </span>
        </div>
        """
        
        self.append(html)
        
        # Reset counters
        self.signals_found = 0
        self.rejected_low_conf = 0
        self.rejected_liquidity = 0
        
        if self.auto_scroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        self._trim_lines()
    
    def _trim_lines(self):
        """Keep only last N lines to prevent memory issues."""
        # This is approximate - Qt doesn't have exact line count
        # We'll clear if document is too large
        doc = self.document()
        if doc.blockCount() > self.max_lines:
            cursor = QtGui.QTextCursor(doc)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            # Remove first 50 blocks
            for _ in range(50):
                cursor.select(QtGui.QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Remove newline
    
    def clear_log(self):
        """Clear all log entries."""
        self.clear()
        self.signals_found = 0
        self.rejected_low_conf = 0
        self.rejected_liquidity = 0


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
    # Signal emitted when close button is clicked (symbol)
    closePositionRequested = QtCore.Signal(str)
    
    def __init__(self, parent=None) -> None:
        super().__init__(0, 10, parent)
        self.setHorizontalHeaderLabels(["Пара", "Плечо", "Вход", "Текущая", "Размер", "SL", "TP", "PNL", "USDT", ""])
        # Don't populate mock data - wait for real data from bot
        # DISABLE sorting - it causes rows to jump and buttons to disconnect
        self.setSortingEnabled(False)
        self.horizontalHeader().setSectionResizeMode(9, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(9, 65)  # Fixed width for close button column (smaller)
        # DISABLE cell selection - no blue highlighting
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)

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
