# Сторонние компоненты

В комплекте сохраняются исходные бинарные Python runtime, Qt/PySide6, Shiboken, Microsoft runtime и PyInstaller runtime. Встроенные PySide6/Shiboken имеют версию 6.8.2.1 по архиву ConferenceDirector.exe. Библиотеки не изменялись. Дополнительные тексты лицензий находятся в THIRD-PARTY-*.txt и включены в установщик; собственная лицензия автора их не заменяет.

Qt/PySide: https://doc.qt.io/qtforpython-6/licenses.html ; Qt 6.8.2.1: https://download.qt.io/archive/qt/6.8/6.8.2/submodules/ ; PySide/Shiboken: https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.8.2.1 . DLL устанавливаются рядом с программой, их можно заменять в собственной рабочей копии. Python: https://github.com/python/cpython ; PyInstaller: https://github.com/pyinstaller/pyinstaller . Microsoft runtime остаётся под исходными условиями Microsoft.

Тексты перенесены из уже подготовленного набора notices MultiToolHub без редактирования; полное происхождение того набора: https://github.com/jeronimo701/MultiToolHub/tree/main/third-party-licenses . Тексты Qt получены из официального дерева qtbase v6.8.2.1. Модификации сторонних библиотек не заявлены.

Тексты LGPL/GPL являются общими текстами лицензий; ссылка на точный исходный тег PySide 6.8.2.1 приведена выше. Декомпилятор ejfkdev/pycdc v0.6.0 применён как внешний инструмент восстановления; его бинарники в приложение не включались: https://github.com/ejfkdev/pycdc .
