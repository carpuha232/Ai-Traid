#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Trade Analysis Script
Monitors bot logs and analyzes trading performance, order execution, and net profit
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from binance.client import Client

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class TradeAnalyzer:
    def __init__(self, config_path='config.json'):
        """Initialize analyzer with Binance API credentials"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_key = config['api']['key']
        api_secret = config['api']['secret']
        self.client = Client(api_key, api_secret)
        
        self.orders_tracked = defaultdict(list)  # symbol -> [orders]
        self.closed_trades = []
        self.duplicates_found = []
        
    def get_account_trades(self, symbol=None, limit=100):
        """Fetch recent trades from Binance"""
        try:
            if symbol:
                trades = self.client.futures_account_trades(symbol=symbol, limit=limit, recvWindow=60000)
            else:
                # Get trades for all symbols
                positions = self.client.futures_position_information(recvWindow=60000)
                all_trades = []
                for pos in positions:
                    sym = pos['symbol']
                    trades = self.client.futures_account_trades(symbol=sym, limit=limit, recvWindow=60000)
                    all_trades.extend(trades)
                return all_trades
            return trades
        except Exception as e:
            print(f"❌ Error fetching trades: {e}")
            return []
    
    def calculate_net_profit(self):
        """Calculate total net profit (realized PNL - commissions) from all trades"""
        try:
            # Get recent trades (last 500)
            all_trades = []
            positions = self.client.futures_position_information(recvWindow=60000)
            
            symbols = set(pos['symbol'] for pos in positions)
            # Also add common symbols
            common = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'SOLUSDT']
            symbols.update(common)
            
            for symbol in symbols:
                try:
                    trades = self.client.futures_account_trades(symbol=symbol, limit=100, recvWindow=60000)
                    all_trades.extend(trades)
                except:
                    pass
            
            total_realized = 0.0
            total_commission = 0.0
            
            for trade in all_trades:
                realized = float(trade.get('realizedPnl', 0))
                commission = float(trade.get('commission', 0))
                total_realized += realized
                total_commission += commission
            
            net_profit = total_realized - total_commission
            
            return {
                'total_realized': total_realized,
                'total_commission': total_commission,
                'net_profit': net_profit,
                'trade_count': len(all_trades)
            }
        except Exception as e:
            print(f"❌ Error calculating net profit: {e}")
            return None
    
    def analyze_closed_trade(self, symbol):
        """Analyze a specific closed trade"""
        try:
            trades = self.client.futures_account_trades(symbol=symbol, limit=50, recvWindow=60000)
            
            if not trades:
                return None
            
            # Group trades by position (same time window)
            position_trades = []
            total_realized = 0.0
            total_commission = 0.0
            
            for trade in trades:
                realized = float(trade.get('realizedPnl', 0))
                commission = float(trade.get('commission', 0))
                total_realized += realized
                total_commission += commission
                
                position_trades.append({
                    'time': datetime.fromtimestamp(trade['time'] / 1000),
                    'price': float(trade['price']),
                    'qty': float(trade['qty']),
                    'side': trade['side'],
                    'realized_pnl': realized,
                    'commission': commission,
                    'commission_asset': trade.get('commissionAsset', 'USDT')
                })
            
            net_pnl = total_realized - total_commission
            
            return {
                'symbol': symbol,
                'total_realized': total_realized,
                'total_commission': total_commission,
                'net_pnl': net_pnl,
                'trade_count': len(position_trades),
                'trades': position_trades,
                'profitable': net_pnl > 0
            }
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")
            return None
    
    def check_open_orders(self):
        """Check for duplicate or orphaned orders"""
        try:
            orders = self.client.futures_get_open_orders(recvWindow=60000)
            positions = self.client.futures_position_information(recvWindow=60000)
            
            # Get symbols with open positions
            position_symbols = {pos['symbol'] for pos in positions if float(pos['positionAmt']) != 0}
            
            # Group orders by symbol and type
            orders_by_symbol = defaultdict(list)
            for order in orders:
                orders_by_symbol[order['symbol']].append(order)
            
            issues = []
            
            # Check for duplicates
            for symbol, symbol_orders in orders_by_symbol.items():
                # Count by type
                type_count = defaultdict(int)
                for order in symbol_orders:
                    order_type = order['type']
                    type_count[order_type] += 1
                
                # Check for duplicates
                for order_type, count in type_count.items():
                    if count > 1:
                        issues.append({
                            'type': 'DUPLICATE',
                            'symbol': symbol,
                            'order_type': order_type,
                            'count': count,
                            'details': f"{count} {order_type} orders for {symbol}"
                        })
            
            # Check for orphaned orders (no position)
            for symbol, symbol_orders in orders_by_symbol.items():
                if symbol not in position_symbols:
                    issues.append({
                        'type': 'ORPHANED',
                        'symbol': symbol,
                        'order_count': len(symbol_orders),
                        'details': f"{len(symbol_orders)} orders but no position for {symbol}"
                    })
            
            return {
                'total_orders': len(orders),
                'symbols_with_orders': len(orders_by_symbol),
                'open_positions': len(position_symbols),
                'issues': issues
            }
            
        except Exception as e:
            print(f"❌ Error checking orders: {e}")
            return None
    
    def generate_report(self):
        """Generate comprehensive analysis report"""
        print("\n" + "="*80)
        print("📊 TRADING ANALYSIS REPORT")
        print("="*80)
        print(f"🕐 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. Net Profit Analysis
        print("\n" + "-"*80)
        print("💰 NET PROFIT ANALYSIS")
        print("-"*80)
        
        profit_data = self.calculate_net_profit()
        if profit_data:
            print(f"   Total Realized PNL:  ${profit_data['total_realized']:>10.2f}")
            print(f"   Total Commission:    ${profit_data['total_commission']:>10.4f}")
            print(f"   Net Profit:          ${profit_data['net_profit']:>10.2f}")
            print(f"   Trade Count:         {profit_data['trade_count']:>10}")
            print(f"   Avg Commission/Trade: ${profit_data['total_commission']/max(1,profit_data['trade_count']):.4f}")
        
        # 2. Open Orders Check
        print("\n" + "-"*80)
        print("📋 OPEN ORDERS CHECK")
        print("-"*80)
        
        order_check = self.check_open_orders()
        if order_check:
            print(f"   Total Open Orders:   {order_check['total_orders']}")
            print(f"   Symbols with Orders: {order_check['symbols_with_orders']}")
            print(f"   Open Positions:      {order_check['open_positions']}")
            
            if order_check['issues']:
                print(f"\n   ⚠️  ISSUES FOUND: {len(order_check['issues'])}")
                for issue in order_check['issues']:
                    emoji = "🔴" if issue['type'] == 'DUPLICATE' else "⚠️"
                    print(f"   {emoji} {issue['type']}: {issue['details']}")
            else:
                print("   ✅ No issues found!")
        
        # 3. Recent Closed Positions
        print("\n" + "-"*80)
        print("📈 RECENT CLOSED POSITIONS")
        print("-"*80)
        
        # Get income history (closed positions)
        try:
            income = self.client.futures_income_history(incomeType='REALIZED_PNL', limit=10, recvWindow=60000)
            
            if income:
                print(f"\n   Last {len(income)} closed positions:\n")
                for item in reversed(income):
                    symbol = item['symbol']
                    pnl = float(item['income'])
                    time_str = datetime.fromtimestamp(item['time']/1000).strftime('%Y-%m-%d %H:%M')
                    emoji = "✅" if pnl > 0 else "❌"
                    print(f"   {emoji} {symbol:<12} ${pnl:>8.2f}  [{time_str}]")
        except Exception as e:
            print(f"   Error fetching income history: {e}")
        
        print("\n" + "="*80)
        print("✅ Report complete")
        print("="*80 + "\n")

def main():
    """Main entry point"""
    print("🤖 Trade Analyzer Starting...")
    
    try:
        analyzer = TradeAnalyzer()
        analyzer.generate_report()
    except FileNotFoundError:
        print("❌ Error: config.json not found!")
        print("   Run this script from BotRusi directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

