#!/usr/bin/env python3
"""
👥 Скрипт для добавления команды в репозиторий AI-Trade
"""

import requests
import json
import sys

def add_collaborator(username, repo_owner, repo_name, token):
    """Добавляет пользователя как collaborator"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/collaborators/{username}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "permission": "push"  # push права (может читать и писать)
    }
    
    try:
        response = requests.put(url, headers=headers, json=data)
        if response.status_code == 204:
            print(f"✅ Пользователь {username} добавлен как collaborator")
            return True
        elif response.status_code == 201:
            print(f"✅ Приглашение отправлено пользователю {username}")
            return True
        else:
            print(f"❌ Ошибка добавления {username}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    print("👥 Добавление команды в репозиторий AI-Trade")
    print("=" * 50)
    
    # Запрашиваем данные
    repo_owner = input("Введите ваше имя пользователя GitHub: ").strip()
    repo_name = input("Введите название репозитория (по умолчанию AI-Trade): ").strip() or "AI-Trade"
    token = input("Введите ваш Personal Access Token: ").strip()
    
    if not repo_owner or not token:
        print("❌ Необходимо указать имя пользователя и токен")
        return False
    
    print(f"\n📋 Добавление команды в репозиторий: {repo_owner}/{repo_name}")
    
    # Список пользователей команды
    team_members = []
    print("\nВведите имена пользователей команды (пустая строка для завершения):")
    
    while True:
        username = input("GitHub username: ").strip()
        if not username:
            break
        team_members.append(username)
    
    if not team_members:
        print("❌ Не указаны пользователи команды")
        return False
    
    # Добавляем каждого пользователя
    success_count = 0
    for username in team_members:
        if add_collaborator(username, repo_owner, repo_name, token):
            success_count += 1
    
    print(f"\n📊 Результат: {success_count}/{len(team_members)} пользователей добавлено")
    
    if success_count > 0:
        print(f"\n🎉 Команда добавлена в репозиторий!")
        print(f"🔗 Репозиторий: https://github.com/{repo_owner}/{repo_name}")
        print("\n📚 Инструкции для команды:")
        print("1. Клонируйте репозиторий:")
        print(f"   git clone https://github.com/{repo_owner}/{repo_name}.git")
        print("2. Установите зависимости:")
        print("   pip install -r requirements.txt")
        print("3. Запустите систему:")
        print("   python trading_dashboard.py")
    
    return success_count > 0

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Добавление команды не завершено")
        sys.exit(1) 