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
	addon_version="2.3.0",
	# Brief changelog for this version
	# Translators: what's new content for the add-on version to be shown in the add-on store
	addon_changelog=_("""v2.3.0 collects everything since 2.0.3.

New: the buffer window. Press NVDA+Enter in a terminal to open the whole scrollback as a browsable snapshot: arrow through it, press H to move between the commands you ran and the errors they produced, follow the table of contents, read columnar output as real tables, and activate web links. NVDA+Shift+Enter opens a jump to line dialog that moves the review cursor to any line, found by its text. In the command layer, Shift+E shows only errors and Shift+C only the commands you ran.

Also new: any terminal NVDA recognizes is supported, not just those on a built-in list, so terminals the add-on used to ignore now work. Find reaches the scrollback on the legacy Windows console, where NVDA can only read the visible screen. And there is an optional word echo for terminals.

Fixed: braille follows the cursor again. Typing did not update the display until you panned away and back, and it never jumped back to the cursor. Key echo also no longer requires turning NVDA's own typing settings off; inside terminals it replaces them.

Security: passwords are no longer spoken by key echo. Characters are masked and completed words are never spoken while the terminal marks input as protected.

Laptop keyboard layout: NVDA+Enter is NVDA's activate-navigator-object command; Terminal Access takes it only inside terminals. Use the command layer's Enter, or reassign in Input Gestures, if you need NVDA's command there.

Requires NVDA 2025.1 or later. Existing settings are preserved on upgrade."""),
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
	"addon/lib/*.py",
]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
excludedFiles: list[str] = [
	"**/__pycache__/*",
	"**/*.pyc",
]

# Base language for the NVDA add-on
# If your add-on is written in a language other than english, modify this variable.
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
# tables and fenced_code render the command tables and JSON examples.
# toc adds id attributes to headings so the in-guide Table of Contents
# links resolve in the generated HTML.
markdownExtensions: list[str] = ["tables", "fenced_code", "toc"]

# Custom braille translation tables
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
symbolDictionaries: SymbolDictionaries = {}
