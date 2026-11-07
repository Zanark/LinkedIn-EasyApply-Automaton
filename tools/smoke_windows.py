"""Exercise the actual frozen GUI/CLI offline in a private temporary workspace."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path


def smoke(bundle: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="lea-frozen-smoke-") as directory:
        workspace = Path(directory)
        env = os.environ.copy()
        env.update(
            LEA_WORKSPACE=str(workspace),
            QT_QPA_PLATFORM="offscreen",
            PYTHONUTF8="1",
            PYTHONIOENCODING="utf-8",
        )
        cli = bundle / "lea.exe"

        def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                [str(cli), *args],
                env=env,
                cwd=workspace,
                capture_output=True,
                timeout=45,
                check=False,
            )
            if result.returncode:
                sys.stderr.write(
                    result.stdout.decode("utf-8", errors="replace")
                    + result.stderr.decode("utf-8", errors="replace")
                )
                result.check_returncode()
            return subprocess.CompletedProcess(
                result.args,
                result.returncode,
                result.stdout.decode("utf-8"),
                result.stderr.decode("utf-8"),
            )

        for args in (
            ["version"],
            ["--help"],
            ["init"],
            ["stats"],
            ["test-form", "How many years of Python experience do you have?"],
        ):
            result = run_cli(args)
            if args == ["version"] and not result.stdout.strip():
                raise RuntimeError("Frozen version command returned no output.")
            print(f"PASS lea {' '.join(args[:1])}")
        with (
            closing(sqlite3.connect(workspace / "database" / "easy_apply.db")) as database,
            database,
        ):
            database.execute(
                "INSERT INTO jobs (url, title, company) VALUES (?, ?, ?)",
                ("https://example.com/jobs/offline", "Offline Example Role", "Example Company"),
            )
            database.execute(
                "INSERT INTO applications (job_id, status) VALUES (last_insert_rowid(), 'dry_run')"
            )
        for fmt in ("csv", "xlsx"):
            target = workspace / f"applications.{fmt}"
            run_cli(["export", "--output", str(target), "--format", fmt])
            if fmt == "csv":
                with target.open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                if len(rows) != 1 or rows[0]["title"] != "Offline Example Role":
                    raise RuntimeError("Frozen CSV export lost the synthetic application.")
            else:
                with zipfile.ZipFile(target) as workbook:
                    if b"Offline Example Role" not in workbook.read("xl/worksheets/sheet1.xml"):
                        raise RuntimeError("Frozen XLSX export lost the synthetic application.")
            print(f"PASS frozen {fmt.upper()} export")
        config = workspace / "configs" / "config.yaml"
        original = config.read_bytes()
        run_cli(["version"])
        if config.read_bytes() != original:
            raise RuntimeError("A subsequent launch replaced an existing configuration.")
        report = workspace / "gui-smoke.json"
        subprocess.run(
            [str(bundle / "EasyApplyAutomaton.exe"), "--smoke-report", str(report)],
            env=env,
            cwd=workspace,
            check=True,
            timeout=45,
        )
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result.get("ok"):
            raise RuntimeError(f"Frozen GUI smoke check failed: {result}")
        print("PASS frozen GUI render, Playwright driver and real sibling CLI child command")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    smoke(parser.parse_args().bundle.resolve())
