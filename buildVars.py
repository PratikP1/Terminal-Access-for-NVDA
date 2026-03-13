# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries

# Since some strings in `addon_info` are translatable,
# we need to include them in the .po files.
# Gettext recognizes only strings given as parameters to the `_` function.
# To avoid initializing translations in this module we simply import a "fake" `_` function
# which returns whatever is given to it as an argument.
from site_scons.site_tools.NVDATool.utils import _


# Add-on information variables
addon_info = AddonInfo(
	# add-on Name/identifier, internal for NVDA
	addon_name="terminalAccess",
	# Add-on summary/title, usually the user visible name of the add-on
	# Translators: Summary/title for this add-on
	# to be shown on installation and add-on information found in add-on store
	addon_summary=_("Terminal Access for NVDA"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-on store
	addon_description=_("""Provides enhanced terminal accessibility for Windows Terminal and PowerShell, enabling screen reader users to efficiently navigate and interact with command-line interfaces. Inspired by TDSR (Terminal Data Structure Reader) and incorporates functionality from both TDSR and Speakup. Advanced features inspired by community suggestions and discussions."""),
	# version
	addon_version="1.3.2",
	# Brief changelog for this version
	# Translators: what's new content for the add-on version to be shown in the add-on store
	addon_changelog=_("""Security fixes, bug fixes, robustness improvements, and 9 new languages."""),
	# Author(s)
	addon_author="Pratik Patel",
	# URL for the add-on documentation support
	addon_url="https://github.com/PratikP1/Terminal-Access-for-NVDA",
	# URL for the add-on repository where the source code can be found
	addon_sourceURL="https://github.com/PratikP1/Terminal-Access-for-NVDA",
	# Documentation file name
	addon_docFileName="readme.html",
	# Minimum NVDA version supported (e.g. "2025.1.0", minor version is optional)
	addon_minimumNVDAVersion="2025.1.0",
	# Last NVDA version supported/tested (e.g. "2024.4.0", ideally more recent than minimum version)
	addon_lastTestedNVDAVersion="2026.1.0",
	# Add-on update channel (default is None, denoting stable releases,
	# and for development releases, use "dev".)
	# Do not change unless you know what you are doing!
	addon_updateChannel=None,
	# Add-on license such as GPL 2
	addon_license="GPL v3",
	# URL for the license document the add-on is licensed under
	addon_licenseURL="https://www.gnu.org/licenses/gpl-3.0.html",
)

# Define the python files that are the sources of your add-on.
# You can either list every file (using "/" as a path separator,
# or use glob expressions.
pythonSources: list[str] = [
	"addon/globalPlugins/*.py",
]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
excludedFiles: list[str] = []

# Base language for the NVDA add-on
# If your add-on is written in a language other than english, modify this variable.
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
# Most add-ons do not require additional Markdown extensions.
markdownExtensions: list[str] = []

# Custom braille translation tables
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
symbolDictionaries: SymbolDictionaries = {}
