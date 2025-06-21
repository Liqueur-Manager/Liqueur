#!/usr/bin/env python3
import os
import sys
import platform
from pathlib import Path
import stat


def setup_environment():
    """Настройка начального окружения с проверкой прав"""
    try:
        # Определяем корневую директорию
        if platform.system() == "Windows":
            root_dir = Path("C:/")
            packages_dir = root_dir / "Liqueur_Packages"
        else:
            # Проверяем возможность записи в корень на Mac/Linux
            test_path = Path("/Liqueur_Packages/test_write")
            try:
                test_path.parent.mkdir(exist_ok=True, parents=True)
                test_path.touch()
                test_path.unlink()
                root_dir = Path("/")
            except PermissionError:
                if platform.system() == "Darwin":
                    print("🔒 SIP защита активна. Использую домашнюю директорию...")
                root_dir = Path.home()

            packages_dir = root_dir / "Liqueur_Packages"

        # Создаем директории
        packages_dir.mkdir(exist_ok=True, parents=True)
        packages_json = packages_dir / "packages.json"

        if not packages_json.exists():
            with open(packages_json, 'w') as f:
                json.dump({}, f)

        # Устанавливаем правильные права
        if platform.system() != "Windows":
            os.chmod(packages_dir, 0o755)  # rwxr-xr-x
            if packages_json.exists():
                os.chmod(packages_json, 0o644)  # rw-r--r--

        print(f"✅ Директория пакетов: {packages_dir}")
        return True

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False


def install_liqueur():
    """Установка основного скрипта"""
    try:
        # Определяем путь для установки
        if platform.system() == "Windows":
            target_dir = Path(os.environ["PROGRAMFILES"]) / "Liqueur"
        else:
            target_dir = Path("/usr/local/bin") if os.access("/usr/local/bin", os.W_OK) else Path.home() / ".local/bin"

        target_dir.mkdir(exist_ok=True, parents=True)
        script_path = target_dir / "Liqueur.py"

        # Копируем скрипт
        current_file = Path(__file__).parent / "Liqueur.py"
        if not current_file.exists():
            raise FileNotFoundError("Файл Liqueur.py не найден в текущей директории")

        shutil.copy(str(current_file), str(script_path))

        # Устанавливаем права
        if platform.system() != "Windows":
            os.chmod(script_path, 0o755)  # rwxr-xr-x

        # Добавляем в PATH (Unix-системы)
        if platform.system() != "Windows":
            rc_file = Path.home() / (".bashrc" if "bash" in os.environ["SHELL"] else ".zshrc")
            if not f"export PATH=$PATH:{target_dir}" in rc_file.read_text():
                with open(rc_file, 'a') as f:
                    f.write(f"\n# Добавлено Liqueur Package Manager\nexport PATH=$PATH:{target_dir}\n")

        print(f"✅ Установлено в: {script_path}")
        if platform.system() != "Windows":
            print(f"ℹ️ Перезапустите терминал или выполните: source {rc_file}")
        return True

    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        return False


def main():
    print("🛠️ Начальная настройка Liqueur Package Manager...")

    if not setup_environment():
        sys.exit(1)

    if "--install" in sys.argv:
        if not install_liqueur():
            sys.exit(1)

    print("\nГотово! Используйте:")
    print("  Liqueur.py install <репозиторий>  # Установка пакета")
    print("  Liqueur.py list                   # Список пакетов")


if __name__ == "__main__":
    import shutil
    import json

    main()