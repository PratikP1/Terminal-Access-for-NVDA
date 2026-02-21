"""
pytest configuration and fixtures for Terminal Access tests.
"""
import sys
import os
from unittest.mock import Mock, MagicMock

import pytest

# Store original module references
_original_modules = {}

# Add the addon directory to the Python path
addon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'addon')
sys.path.insert(0, addon_path)

# Mock NVDA modules that aren't available during testing
# Create a proper GlobalPlugin base class for globalPluginHandler
class MockGlobalPlugin:
    """Mock base class for GlobalPlugin."""
    def __init__(self):
        pass

    def terminate(self):
        pass

globalPluginHandler_mock = MagicMock()
globalPluginHandler_mock.GlobalPlugin = MockGlobalPlugin

sys.modules['globalPluginHandler'] = globalPluginHandler_mock
sys.modules['api'] = MagicMock()
sys.modules['ui'] = MagicMock()
sys.modules['config'] = MagicMock()

# Mock gui module and its submodules properly
gui_mock = MagicMock()
gui_helper_mock = MagicMock()
nvda_controls_mock = MagicMock()
settings_dialogs_mock = MagicMock()

# Create a mock SettingsPanel class
class MockSettingsPanel:
    def __init__(self, parent=None):
        self.parent = parent

settings_dialogs_mock.SettingsPanel = MockSettingsPanel

# Create mock NVDASettingsDialog with categoryClasses
nvda_settings_dialog_mock = MagicMock()
nvda_settings_dialog_mock.categoryClasses = []
settings_dialogs_mock.NVDASettingsDialog = nvda_settings_dialog_mock

sys.modules['gui'] = gui_mock
sys.modules['gui.guiHelper'] = gui_helper_mock
sys.modules['gui.nvdaControls'] = nvda_controls_mock
sys.modules['gui.settingsDialogs'] = settings_dialogs_mock

gui_mock.guiHelper = gui_helper_mock
gui_mock.nvdaControls = nvda_controls_mock
gui_mock.settingsDialogs = settings_dialogs_mock

sys.modules['textInfos'] = MagicMock()
sys.modules['addonHandler'] = MagicMock()
sys.modules['scriptHandler'] = MagicMock()
sys.modules['globalCommands'] = MagicMock()
sys.modules['speech'] = MagicMock()
sys.modules['logHandler'] = MagicMock()
sys.modules['wx'] = MagicMock()

# Mock translation function
import builtins
builtins._ = lambda x: x

# Set up mock config
config_mock = sys.modules['config']
conf_dict = {
    "terminalAccess": {
        "cursorTracking": True,
        "cursorTrackingMode": 1,
        "keyEcho": True,
        "linePause": True,
        "processSymbols": False,
        "punctuationLevel": 2,
        "repeatedSymbols": False,
        "repeatedSymbolsValues": "-_=!",
        "cursorDelay": 20,
        "quietMode": False,
        "verboseMode": False,  # Added verboseMode
        "windowTop": 0,
        "windowBottom": 0,
        "windowLeft": 0,
        "windowRight": 0,
        "windowEnabled": False,
    }
}
# Create a mock conf object that acts like a dict but also has a spec attribute
config_mock.conf = Mock()
config_mock.conf.__getitem__ = lambda self, key: conf_dict[key]
config_mock.conf.__setitem__ = lambda self, key, value: conf_dict.__setitem__(key, value)
config_mock.conf.spec = {}


@pytest.fixture
def mock_terminal():
    """Create a mock terminal object for testing."""
    terminal = Mock()
    terminal.appModule = Mock()
    terminal.appModule.appName = "windowsterminal"
    return terminal


@pytest.fixture
def mock_textinfo():
    """Create a mock TextInfo object for testing."""
    textinfo = Mock()
    textinfo.bookmark = "test_bookmark"
    textinfo.text = "test text"
    textinfo.copy = Mock(return_value=Mock())
    textinfo.expand = Mock()
    textinfo.collapse = Mock()
    textinfo.move = Mock(return_value=1)
    textinfo.compareEndPoints = Mock(return_value=0)
    textinfo.setEndPoint = Mock()
    return textinfo


@pytest.fixture
def reset_config():
    """Reset config to defaults before each test."""
    config_mock = sys.modules['config']
    config_mock.conf["terminalAccess"] = {
        "cursorTracking": True,
        "cursorTrackingMode": 1,
        "keyEcho": True,
        "linePause": True,
        "processSymbols": False,
        "punctuationLevel": 2,
        "repeatedSymbols": False,
        "repeatedSymbolsValues": "-_=!",
        "cursorDelay": 20,
        "quietMode": False,
        "verboseMode": False,
        "windowTop": 0,
        "windowBottom": 0,
        "windowLeft": 0,
        "windowRight": 0,
        "windowEnabled": False,
    }
    yield


@pytest.fixture(autouse=True)
def ensure_mocks():
    """Ensure NVDA mocks are always available in sys.modules."""
    # This fixture runs automatically before each test
    # It ensures that if any test deleted a mock, it's restored
    required_modules = ['config', 'api', 'ui', 'gui', 'globalPluginHandler']

    for module_name in required_modules:
        if module_name not in sys.modules:
            # Restore from our global setup
            if module_name == 'config':
                config_mock = MagicMock()
                conf_dict = {
                    "terminalAccess": {
                        "cursorTracking": True,
                        "cursorTrackingMode": 1,
                        "keyEcho": True,
                        "linePause": True,
                        "processSymbols": False,
                        "punctuationLevel": 2,
                        "repeatedSymbols": False,
                        "repeatedSymbolsValues": "-_=!",
                        "cursorDelay": 20,
                        "quietMode": False,
                        "verboseMode": False,
                        "windowTop": 0,
                        "windowBottom": 0,
                        "windowLeft": 0,
                        "windowRight": 0,
                        "windowEnabled": False,
                    }
                }
                config_mock.conf = Mock()
                config_mock.conf.__getitem__ = lambda self, key: conf_dict[key]
                config_mock.conf.__setitem__ = lambda self, key, value: conf_dict.__setitem__(key, value)
                config_mock.conf.spec = {}
                sys.modules['config'] = config_mock
            else:
                sys.modules[module_name] = MagicMock()

    yield
