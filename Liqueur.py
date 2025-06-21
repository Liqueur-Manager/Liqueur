#!/usr/bin/env python3
import os
import sys
import platform
from pathlib import Path
import json
import shutil
import stat
import time
import requests
import zipfile
import subprocess
import winreg
from typing import Optional, List
from urllib.parse import urlparse

# Конфигурация
ALLOWED_ORG = "Liqueur-Manager"
BASE_GITHUB_URL = "https://github.com"
PACKAGES_DIR = Path("/Liqueur_Packages") if platform.system() != "Windows" else Path("C:/Liqueur_Packages")
PACKAGES_JSON = PACKAGES_DIR / "packages.json"
AUTORUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def print_help():
    """Выводит справку по использованию"""
    help_text = """
Liqueur Package Manager - система управления пакетами

Использование:
  install <репозиторий> [--name <имя>]  Установка пакета
  uninstall <имя_пакета>                Удаление пакета
  list                                   Список установленных пакетов
  help                                   Показать эту справку

Примеры:
  Liqueur install MyRepo
  Liqueur install MyRepo --name MyApp
  Liqueur uninstall OldApp
"""
    print(help_text)


def setup_environment():
    """Настройка рабочей среды"""
    try:
        if platform.system() == "Darwin":
            test_path = Path("/Liqueur_Packages/test_write")
            try:
                test_path.parent.mkdir(exist_ok=True, parents=True)
                test_path.touch()
                test_path.unlink()
            except PermissionError:
                print("🔒 Обнаружена защита SIP. Использую домашнюю директорию...")
                global PACKAGES_DIR, PACKAGES_JSON
                PACKAGES_DIR = Path.home() / "Liqueur_Packages"
                PACKAGES_JSON = PACKAGES_DIR / "packages.json"

        PACKAGES_DIR.mkdir(exist_ok=True, parents=True)
        if not PACKAGES_JSON.exists():
            with open(PACKAGES_JSON, 'w') as f:
                json.dump({}, f)
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)


def add_to_autostart(app_name: str, file_path: Path):
    if platform.system() != "Windows":
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, str(file_path))
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"❌ Ошибка добавления в автозагрузку: {e}")
        return False


def remove_from_autostart(app_name: str):
    if platform.system() != "Windows":
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, app_name)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"⚠️ Не удалось удалить из автозагрузки: {e}")
        return False


def parse_options(pkg_path: Path) -> dict:
    options = {
        "install_name": None,
        "launch_file": None,
        "autorun": False,
        "dependencies": [],
        "add_to_path": False,
        "downloadable": True,
        "official": True,
        "commands": []
    }

    option_file = pkg_path / "option.txt"
    if not option_file.exists():
        return options

    with open(option_file, 'r') as f:
        lines = [line.split('#')[0].strip() for line in f.readlines() if line.strip()]

        if len(lines) > 0 and lines[0].startswith("Name:"):
            options["install_name"] = lines[0].split("Name:")[1].strip().strip('"')

        if len(lines) > 1 and lines[1].startswith("File:"):
            options["launch_file"] = lines[1].split("File:")[1].strip().strip('"')

        if len(lines) > 2:
            options["autorun"] = "true" in lines[2].lower()

        if len(lines) > 3:
            try:
                options["dependencies"] = json.loads(lines[3])
            except:
                pass

        if len(lines) > 4:
            options["add_to_path"] = "true" in lines[4].lower()

        if len(lines) > 5:
            options["downloadable"] = "true" in lines[5].lower()

        if len(lines) > 6:
            options["official"] = "true" in lines[6].lower()

        if len(lines) > 7:
            try:
                options["commands"] = json.loads(lines[7])
            except:
                pass

    return options


def install_dependencies(dependencies: List[str], pkg_path: Path):
    if not dependencies:
        return

    print("🔧 Установка зависимостей...")

    # Предварительная настройка среды
    pip_command = [sys.executable, "-m", "pip", "install"]
    if platform.system() == "Linux":
        pip_command.append("--user")

    for dep in dependencies:
        try:
            # Пропускаем 'python' так как это системная зависимость
            if dep.lower() == "python":
                print("ℹ️ Python уже должен быть установлен в системе")
                continue

            # Специальная обработка PyQt6
            if dep.lower() in ["pyqt6", "pyqt6-tools"]:
                print(f"🔄 Установка {dep}...")

                # Для разных платформ используем разные методы
                if platform.system() == "Linux":
                    try:
                        # Попробуем установить через системный менеджер
                        subprocess.run(["sudo", "apt-get", "install", "-y", "python3-pyqt6"],
                                       check=True)
                    except:
                        # Если не получилось, пробуем через pip с правами пользователя
                        subprocess.run([*pip_command, "PyQt6"], check=True)
                else:
                    # Для Windows/MacOS используем pip
                    subprocess.run([*pip_command, "PyQt6"], check=True)

                # Дополнительно устанавливаем tools если нужно
                if dep.lower() == "pyqt6-tools":
                    subprocess.run([*pip_command, "pyqt6-tools"], check=True)

                print(f"✅ Успешно установлен: {dep}")
                continue

            # Установка других зависимостей
            if dep.startswith(f"{ALLOWED_ORG}/"):
                repo_name = dep.split("/")[1]
                install_package(repo_name)
            else:
                print(f"🔄 Установка {dep}...")
                subprocess.run([*pip_command, dep], check=True)
                print(f"✅ Успешно установлен: {dep}")

        except subprocess.CalledProcessError as e:
            print(f"⚠️ Ошибка при установке {dep}. Пробую альтернативный метод...")

            # Альтернативные методы установки
            try:
                # 1. Попробуем обновить pip
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                               check=True)

                # 2. Попробуем установить с дополнительными флагами
                subprocess.run([*pip_command, "--no-cache-dir", "--force-reinstall", dep],
                               check=True)

                print(f"✅ Установлено после повторной попытки: {dep}")
            except Exception as e:
                print(f"❌ Критическая ошибка при установке {dep}:")
                print(f"   Причина: {str(e)}")
                print("   Попробуйте установить вручную:")
                print(f"   pip install {dep}")

                # Запись в лог ошибки
                with open(pkg_path / "install_errors.log", "a") as log_file:
                    log_file.write(f"Failed to install {dep}: {str(e)}\n")

def download_repo(repo_name: str, target_dir: Path) -> bool:
    try:
        url = f"{BASE_GITHUB_URL}/{ALLOWED_ORG}/{repo_name}/archive/refs/heads/main.zip"
        response = requests.get(url, stream=True)
        response.raise_for_status()

        zip_path = target_dir.with_suffix('.zip')
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir.parent)

        extracted_dir = target_dir.parent / f"{repo_name}-main"
        if extracted_dir.exists():
            extracted_dir.rename(target_dir)

        zip_path.unlink()
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        if 'zip_path' in locals() and zip_path.exists():
            zip_path.unlink()
        return False


def force_remove(path: Path, retries: int = 3, delay: float = 1.0) -> bool:
    for attempt in range(retries):
        try:
            for root, dirs, files in os.walk(path):
                for name in files:
                    file_path = Path(root) / name
                    file_path.chmod(stat.S_IWRITE)
                for name in dirs:
                    dir_path = Path(root) / name
                    dir_path.chmod(stat.S_IWRITE)
            shutil.rmtree(path)
            return True
        except Exception:
            time.sleep(delay)

    try:
        shutil.rmtree(path, ignore_errors=True)
        return True
    except:
        return False


def validate_repo_url(repo_url: str) -> bool:
    try:
        parsed = urlparse(repo_url)
        return parsed.netloc.endswith("github.com") and \
            parsed.path.strip("/").split("/")[0] == ALLOWED_ORG
    except:
        return False


def normalize_repo_url(repo_input: str) -> str:
    if repo_input.startswith(("http://", "https://")):
        return repo_input
    return f"{BASE_GITHUB_URL}/{ALLOWED_ORG}/{repo_input}"


def get_installed_packages() -> dict:
    try:
        with open(PACKAGES_JSON, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_package_info(name: str, repo_url: str):
    packages = get_installed_packages()
    packages[name] = {
        "repo_url": repo_url,
        "path": str(PACKAGES_DIR / name),
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(PACKAGES_JSON, 'w') as f:
        json.dump(packages, f, indent=4)


def execute_commands(commands: List[str], pkg_path: Path):
    if not commands:
        return

    print("⚙️ Выполнение команд...")
    os.chdir(pkg_path)

    for cmd in commands:
        try:
            print(f"$ {cmd}")
            if any(danger in cmd.lower() for danger in ["rm", "del", "format", "taskkill"]):
                confirm = input(f"⚠️ Выполнить опасную команду? (y/n): ")
                if confirm.lower() != 'y':
                    continue

            subprocess.run(cmd, shell=True, check=True)
        except Exception as e:
            print(f"❌ Ошибка выполнения: {cmd}\n{str(e)}")


def install_package(repo_input: str, name: Optional[str] = None):
    try:
        repo_url = normalize_repo_url(repo_input)
        if not validate_repo_url(repo_url):
            print(f"❌ Репозиторий должен принадлежать {ALLOWED_ORG}")
            return

        repo_name = repo_url.split("/")[-1]
        temp_dir = PACKAGES_DIR / f"temp_{repo_name}"

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print(f"🚀 Загрузка '{repo_name}'...")
        if not download_repo(repo_name, temp_dir):
            return

        options = parse_options(temp_dir)

        if not options["official"]:
            print("⚠️ ВНИМАНИЕ: Это НЕ официальный репозиторий!")
            confirm = input("Продолжить установку? (y/n): ")
            if confirm.lower() != 'y':
                shutil.rmtree(temp_dir)
                return

        if not options["downloadable"]:
            print(f"❌ Пакет '{repo_name}' запрещён к скачиванию")
            shutil.rmtree(temp_dir)
            return

        pkg_name = name or options["install_name"] or repo_name
        target_dir = PACKAGES_DIR / pkg_name

        if target_dir.exists():
            print(f"⚠️ Пакет '{pkg_name}' уже установлен!")
            shutil.rmtree(temp_dir)
            return

        shutil.move(temp_dir, target_dir)
        install_dependencies(options["dependencies"], target_dir)

        if options["autorun"] and options["launch_file"]:
            autorun_file = target_dir / options["launch_file"]
            if autorun_file.exists() and add_to_autostart(pkg_name, autorun_file):
                print(f"✅ Добавлено в автозагрузку: {autorun_file}")

        execute_commands(options["commands"], target_dir)

        if options["launch_file"]:
            launch_path = target_dir / options["launch_file"]
            if launch_path.exists():
                print(f"🚀 Запускаю {options['launch_file']}...")
                if platform.system() == "Windows":
                    os.startfile(launch_path)
                else:
                    subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(launch_path)])

        save_package_info(pkg_name, repo_url)
        print(f"✅ Пакет '{pkg_name}' установлен в {target_dir}")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        if 'temp_dir' in locals() and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def uninstall_package(name: str):
    try:
        packages = get_installed_packages()
        if name not in packages:
            print(f"❌ Пакет '{name}' не найден!")
            return

        pkg_path = Path(packages[name]["path"])
        remove_from_autostart(name)

        if not pkg_path.exists():
            print(f"ℹ️ Папка пакета уже удалена")
            del packages[name]
            with open(PACKAGES_JSON, 'w') as f:
                json.dump(packages, f, indent=4)
            return

        print(f"🗑️ Удаление '{name}'...")
        if force_remove(pkg_path):
            del packages[name]
            with open(PACKAGES_JSON, 'w') as f:
                json.dump(packages, f, indent=4)
            print(f"✅ Пакет удалён!")
        else:
            print(f"❌ Не удалось удалить полностью. Попробуйте вручную:\n{pkg_path}")

    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")


def list_packages():
    packages = get_installed_packages()
    if not packages:
        print("📦 Нет установленных пакетов")
    else:
        print("📦 Установленные пакеты:")
        for name, info in packages.items():
            print(f"  • {name} ({info['repo_url']})")
            print(f"    📁 {info['path']}")
            print(f"    ⏱️ {info.get('installed_at', 'дата неизвестна')}")


if __name__ == "__main__":
    setup_environment()

    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "install" and len(sys.argv) >= 3:
        repo = sys.argv[2]
        name = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--name" else None
        install_package(repo, name)
    elif cmd == "uninstall" and len(sys.argv) >= 3:
        uninstall_package(sys.argv[2])
    elif cmd == "list":
        list_packages()
    elif cmd in ("help", "--help", "-h"):
        print_help()
    else:
        print("❌ Неизвестная команда")
        print_help()
        sys.exit(1)