# 🔗 Настройка GitHub для AI-Trade

## 🚨 Проблема с аутентификацией

GitHub больше не поддерживает пароли для Git операций. Нужен **Personal Access Token**.

## 🚀 Быстрое решение

### 1. Создайте Personal Access Token

1. Зайдите на [GitHub.com](https://github.com) и войдите в аккаунт
2. Нажмите на аватар → **Settings**
3. В левом меню: **Developer settings** → **Personal access tokens** → **Tokens (classic)**
4. Нажмите **"Generate new token (classic)"**
5. **Название:** `AI-Trade-Access`
6. **Срок:** 90 дней
7. **Разрешения:** ✅ `repo` (полный доступ к репозиториям)
8. Нажмите **"Generate token"**
9. **Скопируйте токен** (показывается только один раз!)

### 2. Создайте репозиторий на GitHub

1. На GitHub нажмите **"New repository"**
2. **Repository name:** `AI-Trade`
3. **Description:** `Интеллектуальная торговая система для криптовалют`
4. **Visibility:** Public
5. **НЕ ставьте галочки** (README, .gitignore, license)
6. Нажмите **"Create repository"**

### 3. Скопируйте URL репозитория

URL будет: `https://github.com/ваш_username/AI-Trade.git`

### 4. Запустите скрипт настройки

```bash
cd AI-Trade
python setup_github.py
```

### 5. При запросе пароля введите токен

Когда Git попросит пароль, введите ваш **Personal Access Token** (не пароль от GitHub).

## 🔧 Альтернативный способ (вручную)

```bash
# Добавьте remote
git remote add origin https://github.com/ваш_username/AI-Trade.git

# Переименуйте ветку
git branch -M main

# Отправьте код (при запросе пароля введите токен)
git push -u origin main
```

## 🛠️ Устранение проблем

### Ошибка: "Authentication failed"
- Проверьте правильность токена
- Убедитесь, что токен не истек
- Проверьте права токена (должен быть `repo`)

### Ошибка: "Repository not found"
- Проверьте правильность URL репозитория
- Убедитесь, что репозиторий существует

## 📞 Поддержка

Если не получается:
1. Проверьте токен: [GitHub Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Создайте новый токен если старый истек
3. Обратитесь: support@ai-trade.com

---

**Версия:** 2.0.0  
**Дата:** 2024-07-07 