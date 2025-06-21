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
from typing import Optional
from urllib.parse import urlparse

# Конфигурация
ALLOWED_ORG = "Liqueur-Manager"
BASE_GITHUB_URL = "https://github.com"
API_URL = f"https://api.github.com/repos/{ALLOWED_ORG}"
PACKAGES_DIR = Path("/Liqueur_Packages") if platform.system() != "Windows" else Path("C:/Liqueur_Packages")
PACKAGES_JSON = PACKAGES_DIR / "packages.json"


def download_repo(repo_name: str, target_dir: Path) -> bool:
    """Скачивает репозиторий как zip-архив и распаковывает"""
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

        # Переименовываем папку (github добавляет '-main' к имени)
        extracted_dir = target_dir.parent / f"{repo_name}-main"
        if extracted_dir.exists():
            extracted_dir.rename(target_dir)

        zip_path.unlink()
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return False


def force_remove(path: Path, retries: int = 3, delay: float = 1.0) -> bool:
    """Рекурсивно удаляет папку с несколькими попытками"""
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
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1} не удалась: {str(e)}")
            time.sleep(delay)

    try:
        shutil.rmtree(path, ignore_errors=True)
        return True
    except:
        return False


def validate_repo_url(repo_url: str) -> bool:
    """Проверяет принадлежность репозитория к организации"""
    try:
        parsed = urlparse(repo_url)
        if not parsed.netloc.endswith("github.com"):
            return False

        path_parts = parsed.path.strip("/").split("/")
        return len(path_parts) >= 2 and path_parts[0] == ALLOWED_ORG
    except:
        return False


def normalize_repo_url(repo_input: str) -> str:
    """Нормализует URL репозитория"""
    if repo_input.startswith(("http://", "https://")):
        return repo_input
    return f"{BASE_GITHUB_URL}/{ALLOWED_ORG}/{repo_input}"


def setup_environment():
    """Инициализирует рабочую среду"""
    try:
        PACKAGES_DIR.mkdir(exist_ok=True, parents=True)
        if not PACKAGES_JSON.exists():
            with open(PACKAGES_JSON, 'w') as f:
                json.dump({}, f)
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)


def get_installed_packages() -> dict:
    """Возвращает список установленных пакетов"""
    try:
        with open(PACKAGES_JSON, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_package_info(name: str, repo_url: str):
    """Сохраняет метаданные пакета"""
    packages = get_installed_packages()
    packages[name] = {
        "repo_url": repo_url,
        "path": str(PACKAGES_DIR / name),
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(PACKAGES_JSON, 'w') as f:
        json.dump(packages, f, indent=4)


def install_package(repo_input: str, name: Optional[str] = None):
    """Устанавливает пакет из репозитория"""
    try:
        repo_url = normalize_repo_url(repo_input)

        if not validate_repo_url(repo_url):
            print(f"❌ Репозиторий должен принадлежать {ALLOWED_ORG}")
            return

        repo_name = repo_url.split("/")[-1]
        pkg_name = name if name else repo_name
        target_dir = PACKAGES_DIR / pkg_name

        if target_dir.exists():
            print(f"⚠️ Пакет '{pkg_name}' уже установлен!")
            return

        print(f"🚀 Загрузка '{pkg_name}' из {repo_url}...")

        if not download_repo(repo_name, target_dir):
            print("❌ Не удалось скачать пакет")
            return

        save_package_info(pkg_name, repo_url)
        print(f"✅ Пакет '{pkg_name}' установлен в {target_dir}")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


def uninstall_package(name: str):
    """Удаляет установленный пакет"""
    try:
        packages = get_installed_packages()

        if name not in packages:
            print(f"❌ Пакет '{name}' не найден!")
            return

        pkg_path = Path(packages[name]["path"])

        if not pkg_path.exists():
            print(f"ℹ️ Папка пакета '{name}' уже удалена")
            del packages[name]
            with open(PACKAGES_JSON, 'w') as f:
                json.dump(packages, f, indent=4)
            return

        print(f"🗑️ Удаление пакета '{name}'...")

        if force_remove(pkg_path):
            del packages[name]
            with open(PACKAGES_JSON, 'w') as f:
                json.dump(packages, f, indent=4)
            print(f"✅ Пакет '{name}' удалён!")
        else:
            print(f"❌ Не удалось удалить '{name}' полностью")
            print("Советы:")
            print(f"1. Закройте программы, использующие {pkg_path}")
            print(f"2. Запустите от администратора: rmdir /s /q \"{pkg_path}\"")
            print(f"3. Удалите вручную через проводник")

    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")


def list_packages():
    """Выводит список установленных пакетов"""
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
    """Выводит справку по использованию"""
    print("\nLiqueur Package Manager")
    print("Использование:")
    print(f"  install <имя_репозитория> - Установить пакет из {ALLOWED_ORG}")
    print("  uninstall <имя_пакета>     - Удалить пакет")
    print("  list                      - Показать установленные пакеты")
    print("\nПримеры:")
    print(f"  {sys.argv[0]} install Liqueur")
    print(f"  {sys.argv[0]} uninstall Liqueur")


if __name__ == "__main__":
    setup_environment()

    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "install" and len(sys.argv) >= 3:
        repo = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[2] == "--name" else None
        install_package(repo, name)
    elif cmd == "uninstall" and len(sys.argv) >= 3:
        uninstall_package(sys.argv[2])
    elif cmd == "list":
        list_packages()
    else:
        print("❌ Неизвестная команда")
        print_help()
        sys.exit(1)