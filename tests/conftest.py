"""
pytest configuration and fixtures for Terminal Access tests.
"""
import sys
import os
from unittest.mock import Mock, MagicMock

import pytest

# Add the addon directory to the Python path
addon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'addon')
sys.path.insert(0, addon_path)

# Mock NVDA modules that aren't available during testing
sys.modules['globalPluginHandler'] = MagicMock()
sys.modules['api'] = MagicMock()
sys.modules['ui'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['gui'] = MagicMock()
sys.modules['gui.guiHelper'] = MagicMock()
sys.modules['gui.nvdaControls'] = MagicMock()
sys.modules['gui.settingsDialogs'] = MagicMock()
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
        "windowTop": 0,
        "windowBottom": 0,
        "windowLeft": 0,
        "windowRight": 0,
        "windowEnabled": False,
    }
    yield
