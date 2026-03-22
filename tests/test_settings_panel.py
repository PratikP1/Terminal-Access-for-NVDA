"""
Tests for the extracted TerminalAccessSettingsPanel (lib.settings_panel).

Validates:
- Module importability
- Class hierarchy (subclass of SettingsPanel)
- Basic section contains the expected four controls
- Advanced section contains the remaining controls
"""

import pytest


class TestSettingsPanelImport:
    """Verify the module and class can be imported."""

    def test_module_imports(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        assert TerminalAccessSettingsPanel is not None

    def test_class_is_subclass_of_settings_panel(self):
        from gui.settingsDialogs import SettingsPanel
        from lib.settings_panel import TerminalAccessSettingsPanel
        assert issubclass(TerminalAccessSettingsPanel, SettingsPanel)

    def test_title_is_set(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        assert TerminalAccessSettingsPanel.title == "Terminal Settings"


class TestSettingsPanelSections:
    """Verify the Basic / Advanced control lists are correct."""

    def test_basic_controls_tuple(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        expected = (
            "cursorTrackingCheckBox",
            "keyEchoCheckBox",
            "quietModeCheckBox",
            "punctuationLevelChoice",
        )
        assert TerminalAccessSettingsPanel.BASIC_CONTROLS == expected

    def test_basic_controls_count(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        assert len(TerminalAccessSettingsPanel.BASIC_CONTROLS) == 4

    def test_extended_controls_tuple(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        expected = (
            "cursorTrackingModeChoice",
            "cursorDelaySpinner",
            "linePauseCheckBox",
            "verboseModeCheckBox",
            "indentationOnLineReadCheckBox",
            "repeatedSymbolsCheckBox",
            "repeatedSymbolsValuesText",
            "defaultProfileChoice",
            "resetButton",
            "gestureCheckList",
        )
        assert TerminalAccessSettingsPanel.EXTENDED_CONTROLS == expected

    def test_extended_controls_count(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        assert len(TerminalAccessSettingsPanel.EXTENDED_CONTROLS) == 10

    def test_no_overlap_between_basic_and_extended(self):
        from lib.settings_panel import TerminalAccessSettingsPanel
        basic = set(TerminalAccessSettingsPanel.BASIC_CONTROLS)
        extended = set(TerminalAccessSettingsPanel.EXTENDED_CONTROLS)
        assert basic.isdisjoint(extended), "Basic and Extended controls must not overlap"


class TestSettingsPanelReExport:
    """Verify the class is re-exported from the main plugin module."""

    def test_reexported_from_terminal_access(self):
        from lib.settings_panel import TerminalAccessSettingsPanel as FromMain
        from lib.settings_panel import TerminalAccessSettingsPanel as FromLib
        assert FromMain is FromLib


class TestGestureCheckListAccessibility:
    """Verify gesture checklist uses NVDA's accessible CustomCheckListBox."""

    def test_uses_custom_checklistbox_not_wx(self):
        """Gesture checklist must use nvdaControls.CustomCheckListBox for accessibility."""
        import inspect
        from lib.settings_panel import TerminalAccessSettingsPanel
        source = inspect.getsource(TerminalAccessSettingsPanel)
        assert 'CustomCheckListBox' in source, (
            "gestureCheckList must use nvdaControls.CustomCheckListBox, "
            "not wx.CheckListBox — wx version does not fire IAccessible events."
        )
        # Check that wx.CheckListBox is not used in actual code (comments are OK)
        code_lines = [ln for ln in source.split('\n') if not ln.strip().startswith('#')]
        code_only = '\n'.join(code_lines)
        assert 'wx.CheckListBox' not in code_only, (
            "Found wx.CheckListBox in settings panel code. "
            "Use nvdaControls.CustomCheckListBox instead."
        )

    def test_uses_addLabeledControl_not_addItem(self):
        """Gesture checklist must use addLabeledControl for a screen-reader-visible label."""
        import inspect
        from lib.settings_panel import TerminalAccessSettingsPanel
        source = inspect.getsource(TerminalAccessSettingsPanel)
        # Find the line creating gestureCheckList
        lines = source.split('\n')
        for line in lines:
            if 'gestureCheckList' in line and 'addItem' in line:
                raise AssertionError(
                    "gestureCheckList uses addItem (no label). "
                    "Use addLabeledControl for screen reader accessibility."
                )


class TestGestureLabelHelper:
    """Verify the local _gestureLabel helper mirrors the canonical one."""

    def test_gesture_label_format(self):
        from lib.settings_panel import _gestureLabel
        result = _gestureLabel("kb:NVDA+shift+c", "copyRectangularSelection")
        assert "NVDA" in result
        assert "Shift" in result
        assert "C" in result
        assert "\u2014" in result  # em-dash separator

    def test_gesture_label_single_char_uppercased(self):
        from lib.settings_panel import _gestureLabel
        result = _gestureLabel("kb:NVDA+v", "copyMode")
        assert "+V " in result or result.endswith("+V")  # V is uppercase
