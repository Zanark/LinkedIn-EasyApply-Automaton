Qt / Qt for Python redistribution
================================

This distribution uses the unmodified Qt 6.12.0 and PySide6/Shiboken 6.12.0
shared libraries under LGPL version 3. Their package metadata offers
LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. The commercial-license text
shipped in the wheels is retained with the original package notices; no
commercial license is claimed by this application.

The LGPL-3.0 and incorporated GPL-3.0 texts are included in this directory.
The application is MIT-licensed; that does not relicense its dependencies.
You may replace the LGPL shared libraries with compatible modified versions,
and reverse engineer this application for debugging those modifications.
Keep the replacement DLLs/bindings in the matching _internal locations.
Do not treat the ZIP as a single sealed executable.

Corresponding upstream source, build instructions and license information:

Qt for Python / Shiboken 6.12.0:
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/
https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.12.0

Qt 6.12.0 sources (qtbase, qtsvg and qtimageformats):
https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/
https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.12.0
https://code.qt.io/cgit/qt/qtsvg.git/tree/?h=v6.12.0
https://code.qt.io/cgit/qt/qtimageformats.git/tree/?h=v6.12.0

https://doc.qt.io/qtforpython-6/licenses.html
https://www.qt.io/licensing/open-source-lgpl-obligations

Qt PDF, QML, Quick, WebEngine and VirtualKeyboard are not application features
and are excluded from the portable bundle. Other original dependency notices
are adjacent under THIRD_PARTY_NOTICES. Playwright's own driver LICENSE and
NOTICE also remain beside its bundled driver files.
