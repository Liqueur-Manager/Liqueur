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


def setup_environment():
    """Настройка рабочей среды с проверкой прав на Mac"""
    try:
        if platform.system() == "Darwin":
            test_path = Path("/Liqueur_Packages/test_write")
            try:
                test_path.parent.mkdir(exist_ok=True, parents=True)
                test_path.touch()
                test_path.unlink()
            except PermissionError:
                print("🔒 Обнаружена защита SIP. Использую ~/Liqueur_Packages")
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
            try:
                options["commands"] = json.loads(lines[6])
            except:
                pass

    return options


def install_dependencies(dependencies: List[str], pkg_path: Path):
    if not dependencies:
        return

    print("🔧 Установка зависимостей...")
    for dep in dependencies:
        try:
            if dep.startswith(f"{ALLOWED_ORG}/"):
                repo_name = dep.split("/")[1]
                install_package(repo_name)
            else:
                subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)
                print(f"✅ Установлена зависимость: {dep}")
        except Exception as e:
            print(f"⚠️ Не удалось установить {dep}: {str(e)}")


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


def print_help():
    print("\nLiqueur Package Manager")
    print("Использование:")
    print(f"  install <имя_репозитория> [--name <имя_пакета>]")
    print("  uninstall <имя_пакета>")
    print("  list")
    print("\nПример:")
    print(f"  {sys.argv[0]} install MyRepo --name MyApp")


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
    else:
        print("❌ Неизвестная команда")
        print_help()
        sys.exit(1)