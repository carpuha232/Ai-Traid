#!/usr/bin/env python3
"""
🚀 Быстрая настройка GitHub для AI-Trade
"""

import os
import subprocess
import sys

def run_command(command, description):
    """Выполняет команду и показывает результат"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - успешно")
            return True
        else:
            print(f"❌ {description} - ошибка: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - исключение: {e}")
        return False

def main():
    print("🚀 Быстрая настройка GitHub для AI-Trade")
    print("=" * 50)
    
    # Проверяем Git
    if not run_command("git --version", "Проверка Git"):
        print("❌ Git не установлен. Установите Git с https://git-scm.com/")
        return False
    
    # Инициализируем репозиторий
    if not run_command("git init", "Инициализация Git репозитория"):
        return False
    
    # Настраиваем пользователя (если не настроен)
    print("🔧 Настройка Git пользователя...")
    username = input("Введите ваше имя для Git (или нажмите Enter для пропуска): ").strip()
    email = input("Введите ваш email для Git (или нажмите Enter для пропуска): ").strip()
    
    if username:
        run_command(f'git config user.name "{username}"', "Настройка имени пользователя")
    if email:
        run_command(f'git config user.email "{email}"', "Настройка email")
    
    # Добавляем файлы
    if not run_command("git add .", "Добавление файлов"):
        return False
    
    # Создаем первый коммит
    if not run_command('git commit -m "🎉 Initial commit: AI-Trade v2.0.0"', "Создание первого коммита"):
        return False
    
    # Переименовываем ветку в main
    run_command("git branch -M main", "Переименование ветки в main")
    
    # Запрашиваем URL репозитория
    print("\n📋 Создайте репозиторий на GitHub:")
    print("1. Зайдите на https://github.com")
    print("2. Нажмите 'New repository'")
    print("3. Название: AI-Trade")
    print("4. Описание: Интеллектуальная торговая система для криптовалют")
    print("5. Выберите Public")
    print("6. НЕ ставьте галочки (README, .gitignore, license)")
    print("7. Нажмите 'Create repository'")
    
    repo_url = input("\nВведите URL вашего репозитория (например, https://github.com/username/AI-Trade.git): ").strip()
    
    if not repo_url:
        print("❌ URL репозитория не указан")
        return False
    
    # Добавляем remote
    if not run_command(f'git remote add origin "{repo_url}"', "Добавление удаленного репозитория"):
        return False
    
    print("\n🔐 Настройка аутентификации:")
    print("GitHub больше не поддерживает пароли. Нужен Personal Access Token.")
    print("1. Зайдите в GitHub Settings → Developer settings → Personal access tokens")
    print("2. Нажмите 'Generate new token (classic)'")
    print("3. Выберите 'repo' права")
    print("4. Скопируйте токен")
    
    # Пытаемся пушить
    print("\n🚀 Отправка кода в GitHub...")
    print("При запросе пароля введите ваш Personal Access Token")
    
    if run_command("git push -u origin main", "Отправка кода в GitHub"):
        print("\n🎉 Успешно! Ваш код отправлен в GitHub")
        print(f"🔗 Репозиторий: {repo_url}")
        print("\n📚 Следующие шаги:")
        print("1. Добавьте команду в collaborators (Settings → Collaborators)")
        print("2. Настройте GitHub Actions (если нужно)")
        print("3. Запустите систему: python trading_dashboard.py")
        return True
    else:
        print("\n❌ Ошибка отправки. Проверьте:")
        print("1. Правильность URL репозитория")
        print("2. Создание Personal Access Token")
        print("3. Права токена (должен быть 'repo')")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Настройка не завершена. См. docs/GITHUB_SETUP.md для подробностей.")
        sys.exit(1) 