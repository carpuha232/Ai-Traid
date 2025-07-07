"""
🔄 Синхронизация базы знаний с GitHub
Автоматическая загрузка и выгрузка данных для обучения на всех устройствах
"""

import os
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional
import git
from pathlib import Path

class GitHubKnowledgeSync:
    """
    Синхронизация базы знаний с GitHub репозиторием
    """
    
    def __init__(self, repo_url: str = None, branch: str = "knowledge-base", 
                 local_data_dir: str = "learning_data", 
                 remote_data_dir: str = "knowledge_data"):
        """
        Инициализация синхронизации
        
        Args:
            repo_url: URL GitHub репозитория (если None, пытается найти в текущем репозитории)
            branch: Ветка для хранения данных
            local_data_dir: Локальная папка с данными
            remote_data_dir: Папка в репозитории для данных
        """
        self.repo_url = repo_url
        self.branch = branch
        self.local_data_dir = local_data_dir
        self.remote_data_dir = remote_data_dir
        self.repo = None
        self.sync_enabled = True
        
        # Создаем локальную папку
        os.makedirs(self.local_data_dir, exist_ok=True)
        
        # Инициализируем Git репозиторий
        self._init_repository()
    
    def _init_repository(self):
        """Инициализация Git репозитория"""
        try:
            # Пытаемся найти существующий репозиторий
            if os.path.exists('.git'):
                self.repo = git.Repo('.')
                print(f"✅ Найден существующий Git репозиторий: {self.repo.remotes.origin.url if self.repo.remotes else 'Локальный'}")
            else:
                # Создаем новый репозиторий
                self.repo = git.Repo.init('.')
                print("✅ Создан новый Git репозиторий")
            
            # Если указан URL, добавляем remote
            if self.repo_url and not self.repo.remotes:
                self.repo.create_remote('origin', self.repo_url)
                print(f"✅ Добавлен remote: {self.repo_url}")
            
            # Создаем ветку для данных, если её нет
            if self.branch not in [b.name for b in self.repo.branches]:
                self.repo.git.checkout('-b', self.branch)
                print(f"✅ Создана ветка: {self.branch}")
            else:
                self.repo.git.checkout(self.branch)
                print(f"✅ Переключился на ветку: {self.branch}")
            
            # Создаем папку для данных в репозитории
            os.makedirs(self.remote_data_dir, exist_ok=True)
            
            # Добавляем .gitkeep чтобы папка отслеживалась
            gitkeep_file = os.path.join(self.remote_data_dir, '.gitkeep')
            if not os.path.exists(gitkeep_file):
                with open(gitkeep_file, 'w') as f:
                    f.write('# This file ensures the directory is tracked by Git\n')
            
        except Exception as e:
            print(f"⚠️ Ошибка инициализации Git: {e}")
            self.sync_enabled = False
    
    def sync_to_github(self, commit_message: str = None) -> bool:
        """
        Синхронизация данных с GitHub
        
        Args:
            commit_message: Сообщение коммита
            
        Returns:
            bool: Успешность синхронизации
        """
        if not self.sync_enabled or not self.repo:
            print("❌ Синхронизация отключена или репозиторий не инициализирован")
            return False
        
        try:
            # Создаем сообщение коммита
            if not commit_message:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                commit_message = f"🤖 Обновление базы знаний: {timestamp}"
            
            # Копируем данные в папку репозитория
            self._copy_data_to_repo()
            
            # Добавляем все файлы
            self.repo.git.add(self.remote_data_dir)
            
            # Проверяем, есть ли изменения
            if not self.repo.index.diff('HEAD'):
                print("📝 Нет изменений для коммита")
                return True
            
            # Коммитим изменения
            self.repo.index.commit(commit_message)
            print(f"✅ Коммит создан: {commit_message}")
            
            # Пушим в GitHub
            if self.repo.remotes:
                self.repo.remotes.origin.push(self.branch)
                print(f"🚀 Данные отправлены в GitHub (ветка: {self.branch})")
            
            # После push:
            info = self.get_last_commit_info()
            print(f"[GIT] Последний коммит: {info}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации с GitHub: {e}")
            return False
    
    def sync_from_github(self) -> bool:
        """
        Загрузка данных с GitHub
        
        Returns:
            bool: Успешность загрузки
        """
        if not self.sync_enabled or not self.repo:
            print("❌ Синхронизация отключена или репозиторий не инициализирован")
            return False
        
        try:
            # Переключаемся на ветку данных
            self.repo.git.checkout(self.branch)
            
            # Пуллим последние изменения
            if self.repo.remotes:
                self.repo.remotes.origin.pull(self.branch)
                print(f"📥 Данные загружены с GitHub (ветка: {self.branch})")
            
            # После pull:
            info = self.get_last_commit_info()
            print(f"[GIT] Последний коммит: {info}")
            
            # Копируем данные из репозитория в локальную папку
            self._copy_data_from_repo()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка загрузки с GitHub: {e}")
            return False
    
    def _copy_data_to_repo(self):
        """Копирует данные из локальной папки в репозиторий"""
        try:
            # Очищаем папку в репозитории
            if os.path.exists(self.remote_data_dir):
                for file in os.listdir(self.remote_data_dir):
                    if file != '.gitkeep':
                        os.remove(os.path.join(self.remote_data_dir, file))
            
            # Копируем все файлы из локальной папки
            if os.path.exists(self.local_data_dir):
                for file in os.listdir(self.local_data_dir):
                    if file.endswith('.json') or file.endswith('.txt'):
                        src = os.path.join(self.local_data_dir, file)
                        dst = os.path.join(self.remote_data_dir, file)
                        shutil.copy2(src, dst)
            
            print(f"📁 Данные скопированы в репозиторий: {self.remote_data_dir}")
            
        except Exception as e:
            print(f"❌ Ошибка копирования данных: {e}")
    
    def _copy_data_from_repo(self):
        """Копирует данные из репозитория в локальную папку"""
        try:
            # Создаем локальную папку
            os.makedirs(self.local_data_dir, exist_ok=True)
            
            # Копируем все файлы из репозитория
            if os.path.exists(self.remote_data_dir):
                for file in os.listdir(self.remote_data_dir):
                    if file != '.gitkeep' and (file.endswith('.json') or file.endswith('.txt')):
                        src = os.path.join(self.remote_data_dir, file)
                        dst = os.path.join(self.local_data_dir, file)
                        shutil.copy2(src, dst)
            
            print(f"📁 Данные скопированы из репозитория: {self.local_data_dir}")
            
        except Exception as e:
            print(f"❌ Ошибка копирования данных: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Возвращает статус синхронизации"""
        try:
            if not self.repo:
                return {
                    'sync_enabled': False,
                    'repo_initialized': False,
                    'last_commit': None,
                    'branch': None,
                    'remote_url': None
                }
            
            # Получаем информацию о последнем коммите
            last_commit = None
            if self.repo.head.is_valid():
                last_commit = {
                    'hash': self.repo.head.commit.hexsha[:8],
                    'message': self.repo.head.commit.message.strip(),
                    'author': self.repo.head.commit.author.name,
                    'date': datetime.fromtimestamp(self.repo.head.commit.committed_date).isoformat()
                }
            
            return {
                'sync_enabled': self.sync_enabled,
                'repo_initialized': True,
                'last_commit': last_commit,
                'branch': self.repo.active_branch.name,
                'remote_url': self.repo.remotes.origin.url if self.repo.remotes else None,
                'local_data_files': len([f for f in os.listdir(self.local_data_dir) if f.endswith(('.json', '.txt'))]) if os.path.exists(self.local_data_dir) else 0
            }
            
        except Exception as e:
            return {
                'sync_enabled': False,
                'error': str(e)
            }
    
    def merge_knowledge_bases(self) -> Dict[str, Any]:
        """
        Объединяет базы знаний из разных источников
        
        Returns:
            Dict с результатами объединения
        """
        try:
            # Загружаем данные с GitHub
            if self.sync_from_github():
                print("🔄 Объединение баз знаний...")
                
                # Анализируем файлы
                local_files = set()
                remote_files = set()
                
                if os.path.exists(self.local_data_dir):
                    local_files = set([f for f in os.listdir(self.local_data_dir) if f.endswith('.json')])
                
                if os.path.exists(self.remote_data_dir):
                    remote_files = set([f for f in os.listdir(self.remote_data_dir) if f.endswith('.json')])
                
                # Находим новые файлы
                new_files = remote_files - local_files
                
                # Копируем новые файлы
                for file in new_files:
                    src = os.path.join(self.remote_data_dir, file)
                    dst = os.path.join(self.local_data_dir, file)
                    shutil.copy2(src, dst)
                
                return {
                    'success': True,
                    'local_files': len(local_files),
                    'remote_files': len(remote_files),
                    'new_files': len(new_files),
                    'merged_files': list(new_files)
                }
            
            return {'success': False, 'error': 'Не удалось загрузить данные с GitHub'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_backup(self) -> str:
        """Создает резервную копию базы знаний"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"backup_knowledge_{timestamp}"
            
            if os.path.exists(self.local_data_dir):
                shutil.copytree(self.local_data_dir, backup_dir)
                print(f"💾 Резервная копия создана: {backup_dir}")
                return backup_dir
            else:
                print("⚠️ Нет данных для резервного копирования")
                return ""
                
        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return ""
    
    def setup_auto_sync(self, interval_minutes: int = 1):
        """
        Настраивает автоматическую синхронизацию каждую минуту
        """
        try:
            # Создаем скрипт для автоматической синхронизации
            sync_script = f"""#!/bin/bash
# Автоматическая синхронизация базы знаний
cd "{os.getcwd()}"
python -c "
from trading_bot.github_sync import GitHubKnowledgeSync
sync = GitHubKnowledgeSync()
sync.sync_from_github()
sync.sync_to_github('🤖 Автоматическая синхронизация')
"
"""
            
            # Сохраняем скрипт
            script_path = "auto_sync.sh"
            with open(script_path, 'w') as f:
                f.write(sync_script)
            
            # Делаем скрипт исполняемым
            os.chmod(script_path, 0o755)
            
            # Создаем cron задачу (для Linux/Mac)
            cron_job = f"*/{interval_minutes} * * * * cd {os.getcwd()} && ./{script_path}\n"
            
            print(f"✅ Автоматическая синхронизация настроена (каждые {interval_minutes} минут)")
            print(f"📝 Cron задача: {cron_job}")
            print("💡 Для Windows используйте Планировщик задач")
            
            return script_path
            
        except Exception as e:
            print(f"❌ Ошибка настройки автоматической синхронизации: {e}")
            return ""

    def get_last_commit_info(self):
        """Возвращает подробную информацию о последнем коммите и файлах в knowledge_data"""
        try:
            commit = self.repo.head.commit
            files = os.listdir(self.remote_data_dir) if os.path.exists(self.remote_data_dir) else []
            return {
                'commit_hash': commit.hexsha[:8],
                'commit_message': commit.message.strip(),
                'commit_date': datetime.fromtimestamp(commit.committed_date).isoformat(),
                'files': files
            }
        except Exception as e:
            return {'error': str(e)}

class KnowledgeSyncManager:
    """
    Менеджер синхронизации для интеграции с торговым ботом
    """
    
    def __init__(self, dashboard_logic):
        self.dashboard_logic = dashboard_logic
        self.sync = GitHubKnowledgeSync()
        self.last_sync_time = None
    
    def sync_after_learning(self, commit_message: str = None):
        """Синхронизация после завершения обучения"""
        try:
            self.dashboard_logic.add_terminal_message("🔄 Синхронизация с GitHub...", "INFO")
            
            # Создаем резервную копию
            backup_dir = self.sync.create_backup()
            if backup_dir:
                self.dashboard_logic.add_terminal_message(f"💾 Резервная копия: {backup_dir}", "INFO")
            
            # Синхронизируем с GitHub
            if self.sync.sync_to_github(commit_message):
                self.dashboard_logic.add_terminal_message("✅ База знаний синхронизирована с GitHub", "SUCCESS")
                self.last_sync_time = datetime.now()
            else:
                self.dashboard_logic.add_terminal_message("❌ Ошибка синхронизации с GitHub", "ERROR")
                
        except Exception as e:
            self.dashboard_logic.add_terminal_message(f"❌ Ошибка синхронизации: {e}", "ERROR")
    
    def sync_before_learning(self):
        """Синхронизация перед началом обучения"""
        try:
            self.dashboard_logic.add_terminal_message("📥 Загрузка базы знаний с GitHub...", "INFO")
            
            # Объединяем базы знаний
            result = self.sync.merge_knowledge_bases()
            
            if result['success']:
                self.dashboard_logic.add_terminal_message(
                    f"✅ База знаний загружена: {result['new_files']} новых файлов", 
                    "SUCCESS"
                )
            else:
                self.dashboard_logic.add_terminal_message(
                    f"⚠️ База знаний не загружена: {result.get('error', 'Неизвестная ошибка')}", 
                    "WARNING"
                )
                
        except Exception as e:
            self.dashboard_logic.add_terminal_message(f"❌ Ошибка загрузки: {e}", "ERROR")
    
    def get_sync_status_message(self) -> str:
        """Возвращает сообщение о статусе синхронизации"""
        status = self.sync.get_sync_status()
        
        if not status['sync_enabled']:
            return "❌ Синхронизация отключена"
        
        if not status['repo_initialized']:
            return "⚠️ Репозиторий не инициализирован"
        
        msg = f"✅ Синхронизация активна | Ветка: {status['branch']} | Файлов: {status['local_data_files']}"
        
        if status['last_commit']:
            msg += f" | Последний коммит: {status['last_commit']['date'][:10]}"
        
        if self.last_sync_time:
            msg += f" | Последняя синхронизация: {self.last_sync_time.strftime('%H:%M:%S')}"
        
        return msg 