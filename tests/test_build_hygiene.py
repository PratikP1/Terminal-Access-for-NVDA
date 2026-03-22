"""Tests for build hygiene -- catches packaging issues before they reach users.

The root cause of the terminal detection failure was stale .pyc bytecode from
old Python versions being packaged in the .nvda-addon file.  NVDA loaded the
stale bytecode instead of the modified .py source files.  These tests ensure
that never happens again.
"""
import os
import zipfile
import pytest


class TestAddonPackageHygiene:
    """Verify the built .nvda-addon package doesn't contain stale artifacts."""

    ADDON_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "terminalAccess-1.3.3.nvda-addon"
    )

    @pytest.fixture
    def addon_zip(self):
        """Open the built addon if it exists, skip if not built."""
        if not os.path.exists(self.ADDON_PATH):
            pytest.skip("Addon not built -- run 'scons' first")
        return zipfile.ZipFile(self.ADDON_PATH)

    def test_no_pyc_files_in_addon(self, addon_zip):
        """Built addon must not contain any .pyc bytecode files."""
        pyc_files = [n for n in addon_zip.namelist() if n.endswith('.pyc')]
        assert pyc_files == [], (
            f"Stale .pyc files found in addon package: {pyc_files}. "
            f"Delete addon/__pycache__/ directories and rebuild."
        )

    def test_no_pycache_dirs_in_addon(self, addon_zip):
        """Built addon must not contain __pycache__ directories."""
        pycache = [n for n in addon_zip.namelist() if '__pycache__' in n]
        assert pycache == [], (
            f"__pycache__ entries found in addon: {pycache}"
        )

    def test_all_lib_modules_present(self, addon_zip):
        """All lib/ modules must be in the addon package."""
        required = [
            'lib/__init__.py', 'lib/_runtime.py', 'lib/caching.py',
            'lib/config.py', 'lib/gesture_conflicts.py', 'lib/navigation.py',
            'lib/operations.py', 'lib/profiles.py', 'lib/search.py',
            'lib/settings_panel.py', 'lib/text_processing.py',
            'lib/window_management.py',
        ]
        names = addon_zip.namelist()
        for mod in required:
            assert mod in names, f"Missing module in addon: {mod}"

    def test_manifest_present(self, addon_zip):
        """manifest.ini must exist in the addon package."""
        assert 'manifest.ini' in addon_zip.namelist()

    def test_main_plugin_present(self, addon_zip):
        """globalPlugins/terminalAccess.py must exist."""
        assert 'globalPlugins/terminalAccess.py' in addon_zip.namelist()


class TestAddonPathSetup:
    """Verify the plugin adds the addon root to sys.path for lib/ imports."""

    def test_addon_dir_added_to_syspath(self):
        """terminalAccess.py must add its addon root dir to sys.path."""
        import inspect
        from globalPlugins import terminalAccess
        source = inspect.getsource(terminalAccess)
        # Must contain the sys.path setup before lib imports
        assert "sys.path" in source, (
            "terminalAccess.py does not manipulate sys.path. "
            "NVDA only adds globalPlugins/ to the path, so lib/ won't be found."
        )

    def test_lib_config_importable(self):
        """lib.config must be importable (proves sys.path is correct)."""
        from lib.config import confspec, CT_STANDARD
        assert "cursorTracking" in confspec
        assert CT_STANDARD == 1

    def test_lib_runtime_importable(self):
        """lib._runtime must be importable."""
        import lib._runtime as _rt
        assert hasattr(_rt, 'strip_ansi')

    def test_lib_profiles_importable(self):
        """lib.profiles must be importable."""
        from lib.profiles import _SUPPORTED_TERMINALS
        assert "windowsterminal" in _SUPPORTED_TERMINALS


class TestBuildConfigExcludesPycache:
    """Verify build configuration prevents __pycache__ from being packaged."""

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))

    def test_gitignore_excludes_pycache(self):
        """__pycache__/ must be in .gitignore."""
        gitignore_path = os.path.join(self.ROOT_DIR, ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()
        assert "__pycache__" in content, (
            ".gitignore does not exclude __pycache__/ -- "
            "stale bytecode could be committed and packaged."
        )

    def test_buildvars_excludes_pycache(self):
        """buildVars.excludedFiles must block __pycache__ from the addon."""
        import importlib
        import sys
        # Import buildVars from project root
        spec = importlib.util.spec_from_file_location(
            "buildVars_check",
            os.path.join(self.ROOT_DIR, "buildVars.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Temporarily mock the site_scons imports that buildVars needs
        saved = {}
        for name in list(sys.modules):
            if name.startswith("site_scons"):
                saved[name] = sys.modules.pop(name)

        # Provide minimal stubs so buildVars can import
        from unittest.mock import MagicMock
        from types import ModuleType
        site_scons = ModuleType("site_scons")
        site_tools = ModuleType("site_scons.site_tools")
        nvda_tool = ModuleType("site_scons.site_tools.NVDATool")
        typings = ModuleType("site_scons.site_tools.NVDATool.typings")
        utils = ModuleType("site_scons.site_tools.NVDATool.utils")

        # AddonInfo just needs to behave like a dict-like or dataclass
        typings.AddonInfo = lambda **kw: kw
        typings.BrailleTables = dict
        typings.SymbolDictionaries = dict
        utils._ = lambda x: x

        sys.modules["site_scons"] = site_scons
        sys.modules["site_scons.site_tools"] = site_tools
        sys.modules["site_scons.site_tools.NVDATool"] = nvda_tool
        sys.modules["site_scons.site_tools.NVDATool.typings"] = typings
        sys.modules["site_scons.site_tools.NVDATool.utils"] = utils

        try:
            spec.loader.exec_module(mod)
            excluded = mod.excludedFiles
            has_pycache_pattern = any("__pycache__" in pat for pat in excluded)
            has_pyc_pattern = any(".pyc" in pat for pat in excluded)
            assert has_pycache_pattern, (
                f"buildVars.excludedFiles {excluded} does not block __pycache__"
            )
            assert has_pyc_pattern, (
                f"buildVars.excludedFiles {excluded} does not block .pyc files"
            )
        finally:
            # Restore original modules
            for name in list(sys.modules):
                if name.startswith("site_scons"):
                    del sys.modules[name]
            sys.modules.update(saved)
            if "buildVars_check" in sys.modules:
                del sys.modules["buildVars_check"]
