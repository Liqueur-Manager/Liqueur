import os
import sys
import platform
from pathlib import Path


def create_packages_dir():
    """Создаёт папку Liqueur_Packages в корне системы"""
    try:
        # Определяем корневой путь в зависимости от ОС
        if platform.system() == "Windows":
            root = "C:\\"
            dir_name = "Liqueur_Packages"
        else:  # Linux/Mac
            root = "/"
            dir_name = "Liqueur_Packages"

        # Полный путь к папке
        target_dir = Path(root) / dir_name

        # Проверяем и создаём папку
        if not target_dir.exists():
            target_dir.mkdir()
            print(f"✅ Папка создана: {target_dir}")

            # Устанавливаем правильные права на Linux/Mac
            if platform.system() != "Windows":
                os.chmod(target_dir, 0o755)  # rwxr-xr-x
        else:
            print(f"ℹ️ Папка уже существует: {target_dir}")

        return str(target_dir)

    except PermissionError:
        print(f"❌ Ошибка: Нет прав для создания папки в {root}!")
        print("Запустите скрипт с правами администратора/root:")
        print("  Linux/Mac: sudo python First_setup.py")
        print("  Windows: Запустите от имени администратора")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🛠️ Настройка папки Liqueur_Packages...")
    path = create_packages_dir()
    print(f"Готово! Папка для пакетов: {path}")