# ЛОГИКА ЗАЩИТЫ ПОЗИЦИЙ

## 📋 ОПИСАНИЕ ПРОБЛЕМЫ

**Проблема:** Одновременно работали emergency stop (у цены ликвидации) и progressive stop (в цене -% ROI), хотя должны работать по разным условиям.

## ✅ ПРАВИЛЬНАЯ ЛОГИКА

### MODE 1: УБЫТОК (ROI < 0%)
**Активируется:**
- Emergency Stop (страховочный ордер у цены ликвидации)
- Averaging Order (добор позиции по Мартингейлу)

**Отменяется:**
- Progressive Stop (если был активен)

**Настройки:**
- `emergency_stop_enabled`: true
- `emergency_stop_roi_level`: -85.0% (уровень защиты)
- `emergency_stop_safety_margin`: 0.5% (отступ от ликвидации)
- `averaging_down_enabled`: true
- `averaging_trigger_distance_from_liq`: 15.0% (расстояние от ликвидации)

### MODE 2: МАЛЫЙ ПРОФИТ (0% ≤ ROI < activation_pnl%)
**Активируется:**
- НИЧЕГО (нет защиты)

**Отменяется:**
- Emergency Stop (ОБЯЗАТЕЛЬНО!)
- Averaging Order
- Progressive Stop (если был активен)

**Настройки:**
- `stepped_stop_activation_pnl`: 10.0% (порог активации progressive stop)

### MODE 3: БОЛЬШОЙ ПРОФИТ (ROI ≥ activation_pnl%)
**Активируется:**
- Progressive Stop (защитный стоп-лосс, trailing stop)

**Отменяется:**
- Emergency Stop (ОБЯЗАТЕЛЬНО перед активацией!)
- Averaging Order

**Настройки:**
- `stepped_stop_enabled`: true
- `stepped_stop_activation_pnl`: 10.0% (порог активации)
- Progressive stop работает как trailing stop:
  - До 100%: шаг 10% (стоп отстает на 10%)
  - После 100%: шаг 20% (стоп отстает на 20%)

## 🔧 ИСПРАВЛЕНИЯ

1. **Добавлена обязательная отмена emergency stop при ROI ≥ 0%**
   - В MODE 2 (0% ≤ ROI < activation_pnl%)
   - В MODE 3 (ROI ≥ activation_pnl%) - ПЕРЕД активацией progressive stop

2. **Исправлена логика переключения режимов**
   - Emergency stop отменяется при переходе в прибыль
   - Progressive stop активируется только при ROI ≥ activation_pnl%

3. **Добавлена очистка состояния**
   - Всегда очищаются флаги и order IDs при отмене
   - Даже если отмена не удалась, состояние очищается

## ⚙️ НАСТРОЙКИ В config.json

```json
{
  "risk": {
    "emergency_stop_enabled": true,
    "emergency_stop_roi_level": -85.0,
    "emergency_stop_safety_margin": 0.5,
    "emergency_stop_activation_roi": 0.0,
    "emergency_stop_cancel_roi": 0.0,
    
    "stepped_stop_enabled": true,
    "stepped_stop_activation_pnl": 10.0,
    
    "averaging_down_enabled": true,
    "averaging_trigger_distance_from_liq": 15.0,
    "averaging_martingale_enabled": true,
    "averaging_max_count": 50
  }
}
```

## 📊 ЛОГИКА РАБОТЫ

```
ROI < 0%:
  ✅ Emergency Stop (у ликвидации)
  ✅ Averaging Order (добор)
  ❌ Progressive Stop (отменен)

0% ≤ ROI < activation_pnl%:
  ❌ Emergency Stop (ОТМЕНЕН!)
  ❌ Averaging Order (отменен)
  ❌ Progressive Stop (не активирован)

ROI ≥ activation_pnl%:
  ❌ Emergency Stop (ОТМЕНЕН!)
  ❌ Averaging Order (отменен)
  ✅ Progressive Stop (активен, trailing)
```

## 🎯 КЛЮЧЕВЫЕ МОМЕНТЫ

1. **Emergency Stop** работает ТОЛЬКО при ROI < 0%
2. **Progressive Stop** работает ТОЛЬКО при ROI ≥ activation_pnl%
3. **Emergency Stop ОБЯЗАТЕЛЬНО отменяется** при ROI ≥ 0%
4. **Progressive Stop активируется** только при ROI ≥ activation_pnl%
5. **Нет конфликтов** - только один тип защиты активен в каждый момент


