"""Exercise the real SCons graph and ZIP builder in disposable projects."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


@pytest.fixture
def build_project(tmp_path):
	"""Copy build tooling without runtime code or external gettext inputs."""
	root = Path(__file__).resolve().parents[1]
	for name in ("sconstruct", "buildVars.py", "manifest.ini.tpl", "manifest-translated.ini.tpl", "style.css"):
		shutil.copy2(root / name, tmp_path / name)
	shutil.copytree(root / "site_scons", tmp_path / "site_scons", ignore=shutil.ignore_patterns("__pycache__"))
	for directory in ("addon/globalPlugins", "addon/lib", "addon/doc/en"):
		(tmp_path / directory).mkdir(parents=True)
	(tmp_path / "addon/globalPlugins/main.py").write_bytes(b"VALUE = 1\n")
	(tmp_path / "addon/lib/helper.py").write_bytes(b"VALUE = 1\n")
	(tmp_path / "addon/doc/en/readme.md").write_text("# Maintained guide\n", encoding="utf-8")
	return tmp_path


def run_scons(project, *arguments):
	"""Run SCons only inside the disposable project."""
	result = subprocess.run(
		[sys.executable, "-m", "SCons", "-Q", *arguments], cwd=project,
		capture_output=True, text=True, timeout=60,
	)
	assert result.returncode == 0, result.stdout + result.stderr
	return result.stdout


def test_clean_preserves_maintained_guide(build_project):
	"""Cleaning generated outputs must preserve the author's Markdown source."""
	guide = build_project / "addon/doc/en/readme.md"
	original = guide.read_bytes()
	run_scons(build_project)
	assert (guide.with_suffix(".html")).is_file()
	run_scons(build_project, "-c")
	assert guide.is_file(), "scons -c deleted the maintained guide source"
	assert guide.read_bytes() == original
	assert not guide.with_suffix(".html").exists()
	assert not list(build_project.glob("*.nvda-addon"))


def test_library_edit_updates_existing_package(build_project):
	"""An incremental package must contain the newly edited library source."""
	run_scons(build_project)
	package = next(build_project.glob("*.nvda-addon"))
	with zipfile.ZipFile(package) as archive:
		assert archive.read("lib/helper.py") == b"VALUE = 1\n"
	(build_project / "addon/lib/helper.py").write_bytes(b"VALUE = 2\n")
	run_scons(build_project)
	with zipfile.ZipFile(package) as archive:
		assert archive.read("lib/helper.py") == b"VALUE = 2\n"
