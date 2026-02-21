import os.path

# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

# Full gettext (please don't change)
_ = lambda x: x

# Add-on information variables
addon_info = {
	# add-on Name/identifier
	"addon_name": "TDSR",
	# Add-on summary
	"addon_summary": _("Terminal Data Structure Reader for NVDA"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-ons manager
	"addon_description": _("""Provides enhanced terminal accessibility for Windows Terminal and PowerShell, enabling screen reader users to efficiently navigate and interact with command-line interfaces using TDSR-inspired features."""),
	# version
	"addon_version": "1.0.22",
	# Author(s)
	"addon_author": "TDSR for NVDA Contributors",
	# URL for the add-on documentation support
	"addon_url": "https://github.com/PratikP1/TDSR-for-NVDA",
	# Documentation file name
	"addon_docFileName": "readme.html",
	# Minimum NVDA version supported
	"addon_minimumNVDAVersion": "2019.3.0",
	# Last NVDA version confirmed to be compatible
	"addon_lastTestedNVDAVersion": "2026.1.0",
	# Add-on update channel
	"addon_updateChannel": None,
}

# Define the python files that are the sources of your add-on.
# You can use glob expressions here, they will be expanded.
pythonSources = [
	os.path.join("addon", "globalPlugins", "*.py"),
]

# Files that contain strings for translation. Usually your python sources
i18nSources = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
excludedFiles = []
