import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.app_config import get_icon_path
from ui.main_window import MainWindow


def _set_windows_app_id() -> None:
    """
    Задаёт AppUserModelID на Windows, чтобы панель задач показывала иконку
    приложения, а не общий значок Python. Безопасно игнорируется на других ОС.
    """
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("raskroy.zit.calculator")
    except Exception:
        pass


def main() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)

    # иконка приложения — для всех окон и для панели задач Windows
    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())