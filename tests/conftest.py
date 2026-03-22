"""
pytest configuration and fixtures for Terminal Access tests.
"""
import sys
import os
import types
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
    """Mock base class for GlobalPlugin.

    Mirrors the NVDA ScriptableObject gesture API so tests can verify
    bind/unbind behavior that affects the Input Gestures dialog.
    """
    def __init__(self):
        self._gestureMap = {}

    def terminate(self):
        pass

    def bindGesture(self, gestureIdentifier, scriptName):
        self._gestureMap[gestureIdentifier] = scriptName

    def bindGestures(self, gestureMap):
        self._gestureMap.update(gestureMap)

    def removeGestureBinding(self, gestureIdentifier):
        self._gestureMap.pop(gestureIdentifier, None)

    def clearGestureBindings(self):
        self._gestureMap.clear()

    def getScript(self, gesture):
        """Mock getScript: look up gesture in _gestureMap and return the script method."""
        for identifier in gesture.normalizedIdentifiers:
            scriptName = self._gestureMap.get(identifier)
            if scriptName:
                return getattr(self, f"script_{scriptName}", None)
        return None

globalPluginHandler_mock = MagicMock()
globalPluginHandler_mock.GlobalPlugin = MockGlobalPlugin

sys.modules['globalPluginHandler'] = globalPluginHandler_mock
sys.modules['api'] = MagicMock()
sys.modules['ui'] = MagicMock()
sys.modules['config'] = MagicMock()

# Mock braille module
braille_mock = MagicMock()
braille_mock.handler = MagicMock()
braille_mock.handler.displaySize = 40  # Simulated 40-cell display
braille_mock.handler.message = MagicMock()
braille_mock.handler.handleCaretMove = MagicMock()
sys.modules['braille'] = braille_mock

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

# Provide a scriptHandler module with a real decorator and repeat counter
scriptHandler_mock = types.ModuleType("scriptHandler")

def _script_decorator(description=None, gesture=None, gestures=None, **kwargs):
    """Return the function unchanged while preserving gesture metadata for tests."""
    def decorator(func):
        gesture_list = []
        if gesture:
            gesture_list.append(gesture)
        if gestures:
            if isinstance(gestures, (list, tuple, set)):
                gesture_list.extend(list(gestures))
            else:
                gesture_list.append(gestures)
        # Store gestures on the function for introspection in tests if needed
        func.__gestures__ = gesture_list
        return func
    return decorator

def _get_last_script_repeat_count():
    return 0

scriptHandler_mock.script = _script_decorator
scriptHandler_mock.getLastScriptRepeatCount = _get_last_script_repeat_count
sys.modules['scriptHandler'] = scriptHandler_mock
sys.modules['globalCommands'] = MagicMock()
sys.modules['speech'] = MagicMock()
sys.modules['tones'] = MagicMock()
sys.modules['logHandler'] = MagicMock()
sys.modules['wx'] = MagicMock()

# Mock characterProcessing with a realistic processSpeechSymbol
char_processing_mock = MagicMock()
def _mock_process_speech_symbol(locale, symbol):
    """Mock that mirrors NVDA's behavior: returns symbol unchanged if no mapping."""
    return symbol  # Default: no mapping (tests can override per-test)
char_processing_mock.processSpeechSymbol = _mock_process_speech_symbol
sys.modules['characterProcessing'] = char_processing_mock

# Mock languageHandler
lang_handler_mock = MagicMock()
lang_handler_mock.getLanguage = MagicMock(return_value="en")
sys.modules['languageHandler'] = lang_handler_mock

# Mock translation function
import builtins
builtins._ = lambda x: x

# Populate runtime registry with test defaults so lib.search works
import lib._runtime as _rt
_rt.api_module = sys.modules['api']
_rt.webbrowser_module = MagicMock()


def _default_conf_dict():
    """Single source of truth for the default config dict."""
    return {
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
            "indentationOnLineRead": False,
            "windowTop": 0,
            "windowBottom": 0,
            "windowLeft": 0,
            "windowRight": 0,
            "windowEnabled": False,
            "unboundGestures": "",
        },
        "keyboard": {
            "speakTypedCharacters": False,
        },
    }


# Set up mock config using the single source of truth
config_mock = sys.modules['config']
conf_dict = _default_conf_dict()
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
    """Reset config to defaults before each test.

    Note: ensure_mocks (autouse) already resets config before every test.
    This fixture exists for backward compatibility with tests that
    explicitly request it.
    """
    yield


@pytest.fixture(autouse=True, scope="session")
def _prevent_helper_spawn():
    """Prevent tests from spawning a real helper process.

    The ``_get_helper()`` wrapper in ``terminalAccess.py`` would otherwise
    find the built EXE and spawn it, leaving a zombie process that blocks
    pytest from exiting.

    We patch at both levels:
    - ``native.termaccess_bridge.get_helper`` (new calls)
    - ``globalPlugins.terminalAccess._get_helper`` (already-imported reference)
    """
    originals = {}
    try:
        from native import termaccess_bridge
        originals["bridge_get"] = termaccess_bridge.get_helper
        originals["bridge_stop"] = termaccess_bridge.stop_helper
        termaccess_bridge.get_helper = lambda: None
        termaccess_bridge.stop_helper = lambda: None
    except ImportError:
        pass

    try:
        from globalPlugins import terminalAccess
        originals["plugin_get"] = terminalAccess._get_helper
        originals["plugin_stop"] = terminalAccess._stop_helper
        terminalAccess._get_helper = lambda: None
        terminalAccess._stop_helper = lambda: None
    except (ImportError, AttributeError):
        pass

    yield

    # Restore originals
    if "bridge_get" in originals:
        from native import termaccess_bridge
        termaccess_bridge.get_helper = originals["bridge_get"]
        termaccess_bridge.stop_helper = originals["bridge_stop"]
    if "plugin_get" in originals:
        from globalPlugins import terminalAccess
        terminalAccess._get_helper = originals["plugin_get"]
        terminalAccess._stop_helper = originals["plugin_stop"]


# Snapshot of sys.modules after initial mock setup — used by ensure_mocks
# to restore any module that a test deleted or replaced.
_MOCK_SNAPSHOT = {
    name: sys.modules[name]
    for name in [
        'config', 'api', 'ui', 'gui', 'gui.guiHelper', 'gui.nvdaControls',
        'gui.settingsDialogs', 'globalPluginHandler', 'textInfos',
        'addonHandler', 'scriptHandler', 'globalCommands', 'speech',
        'tones', 'logHandler', 'wx', 'braille',
        'characterProcessing', 'languageHandler',
    ]
    if name in sys.modules
}


@pytest.fixture(autouse=True)
def ensure_mocks():
    """Ensure NVDA mocks and config are in a clean state for every test.

    Restores deleted modules and resets the shared config dict so
    mutations from one test don't leak into the next.
    """
    # Restore any deleted modules
    for name, original in _MOCK_SNAPSHOT.items():
        if name not in sys.modules:
            sys.modules[name] = original

    # Reset config dict to defaults before each test
    config_mock = sys.modules.get('config')
    if config_mock is not None:
        fresh = _default_conf_dict()
        try:
            config_mock.conf.__getitem__ = lambda self, key: fresh[key]
            config_mock.conf.__setitem__ = lambda self, key, value: fresh.__setitem__(key, value)
            config_mock.conf.spec = {}
        except (AttributeError, TypeError):
            pass

    yield


@pytest.fixture
def make_focus():
    """Factory fixture for creating mock NVDA focus objects.

    Usage: obj = make_focus("windowsterminal")
    """
    def _make(app_name, window_class="ConsoleWindowClass"):
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = app_name
        obj.windowClassName = window_class
        obj.windowHandle = 0x12345
        obj.windowText = ""
        return obj
    return _make


@pytest.fixture
def make_plugin():
    """Create a GlobalPlugin instance with mocked NVDA dependencies."""
    def _make():
        from globalPlugins.terminalAccess import GlobalPlugin
        return GlobalPlugin()
    return _make


@pytest.fixture
def plugin_with_terminal(make_focus, make_plugin):
    """Create a GlobalPlugin wired to a mock terminal.

    Returns (plugin, terminal_mock).
    """
    def _make(app_name="windowsterminal"):
        plugin = make_plugin()
        terminal = make_focus(app_name)
        plugin.isTerminalApp = Mock(return_value=True)
        plugin._boundTerminal = terminal
        return plugin, terminal
    return _make
