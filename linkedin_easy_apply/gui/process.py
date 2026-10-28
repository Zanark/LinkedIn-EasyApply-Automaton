"""Run CLI commands from the GUI and stream their output live.

A :class:`QProcess` is used rather than ``subprocess`` so output arrives through
the Qt event loop: the window stays responsive during a long crawl, and the log
appears line by line instead of in one lump at the end.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

__all__ = ["CommandRunner", "child_environment", "start_detached"]


def child_environment() -> QProcessEnvironment:
    """Environment for child CLI processes.

    Unbuffered Python so log lines arrive as they happen rather than when the
    pipe buffer fills, and colour disabled so Rich/Loguru ANSI escapes do not
    show up as noise in a plain text console.
    """
    environment = QProcessEnvironment.systemEnvironment()
    environment.insert("PYTHONUNBUFFERED", "1")
    environment.insert("NO_COLOR", "1")
    environment.insert("TERM", "dumb")
    return environment


def start_detached(argv: list[str], working_directory: Path) -> bool:
    """Start a command that outlives the window (used for the dashboard)."""
    process = QProcess()
    process.setProgram(argv[0])
    process.setArguments(argv[1:])
    process.setWorkingDirectory(str(working_directory))
    process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
    started, _pid = process.startDetached()
    return bool(started)


class CommandRunner(QObject):
    """Owns at most one child process and reports its lifecycle."""

    started_command = Signal(str)  # the full command line
    output = Signal(str)  # one chunk of combined stdout/stderr
    finished = Signal(int, str)  # exit code, human-readable status

    def __init__(self, working_directory: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cwd = Path(working_directory)
        self._process: QProcess | None = None
        self._stopping = False

    # -- state ---------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.NotRunning

    # -- control -------------------------------------------------------------
    def start(self, argv: list[str]) -> bool:
        """Launch *argv*. Returns False when a command is already running."""
        if self.busy:
            return False
        process = QProcess(self)
        process.setWorkingDirectory(str(self._cwd))
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.setProcessEnvironment(child_environment())

        process.readyReadStandardOutput.connect(self._drain)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        self._process = process
        self._stopping = False
        process.start(argv[0], argv[1:])
        if not process.waitForStarted(5000):
            self._process = None
            self.finished.emit(-1, f"Could not start: {argv[0]}")
            return False
        self.started_command.emit(" ".join(argv))
        return True

    def stop(self) -> None:
        """Ask the child to exit, escalating to a kill if it ignores us."""
        if not self.busy or self._process is None:
            return
        self._stopping = True
        self._process.terminate()
        if not self._process.waitForFinished(4000):
            self._process.kill()

    # -- plumbing ------------------------------------------------------------
    def _drain(self) -> None:
        if self._process is None:
            return
        raw = bytes(self._process.readAllStandardOutput())
        if raw:
            self.output.emit(raw.decode("utf-8", errors="replace"))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._process = None
            self.finished.emit(-1, "The command failed to start.")

    def _on_finished(self, exit_code: int, status: QProcess.ExitStatus) -> None:
        self._drain()
        self._process = None
        if self._stopping:
            message = "Stopped."
        elif status == QProcess.CrashExit:
            message = "The command was terminated."
        elif exit_code == 0:
            message = "Finished successfully."
        else:
            message = f"Finished with exit code {exit_code}."
        self._stopping = False
        self.finished.emit(exit_code, message)
