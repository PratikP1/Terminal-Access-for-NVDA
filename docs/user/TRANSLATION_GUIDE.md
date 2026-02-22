# Terminal Access for NVDA - Translation Guide

**Version:** 1.0.32+
**Last Updated:** 2026-02-21

## Overview

This guide explains how to contribute translations for Terminal Access for NVDA. The add-on uses the standard gettext internationalization framework used by NVDA itself.

## Translation Files

### File Structure

```
addon/
└── locale/
    ├── tdsr.pot           # Translation template (DO NOT EDIT)
    ├── es/                # Spanish
    │   └── LC_MESSAGES/
    │       └── nvda.po    # Spanish translation file
    ├── fr/                # French
    │   └── LC_MESSAGES/
    │       └── nvda.po
    ├── de/                # German
    │   └── LC_MESSAGES/
    │       └── nvda.po
    ├── pt/                # Portuguese
    │   └── LC_MESSAGES/
    │       └── nvda.po
    ├── zh_CN/             # Chinese (Simplified)
    │   └── LC_MESSAGES/
    │       └── nvda.po
    ├── zh_TW/             # Chinese (Traditional)
    │   └── LC_MESSAGES/
    │       └── nvda.po
    ├── ja/                # Japanese
    │   └── LC_MESSAGES/
    │       └── nvda.po
    └── ru/                # Russian
        └── LC_MESSAGES/
            └── nvda.po
```

### File Types

- **`.pot` (Template)**: Master translation template containing all translatable strings
- **`.po` (Translation)**: Language-specific translation files
- **`.mo` (Compiled)**: Binary compiled translations (generated automatically during build)

## How to Contribute Translations

### Method 1: Using Poedit (Recommended for Translators)

1. **Download and Install Poedit**
   - Download from: https://poedit.net/
   - Available for Windows, macOS, and Linux
   - Free for open source projects

2. **Open Translation File**
   - Open the `.po` file for your language: `addon/locale/<lang>/LC_MESSAGES/nvda.po`
   - Or create a new translation from `addon/locale/tdsr.pot`

3. **Translate Strings**
   - Poedit shows untranslated strings highlighted
   - Enter translations in the bottom panel
   - Use translation memory and suggestions when available

4. **Save and Test**
   - Save the `.po` file
   - Build the add-on to test your translations
   - Install and verify in NVDA

5. **Submit Translation**
   - Create a pull request on GitHub with your changes
   - Or email the `.po` file to the maintainers

### Method 2: Manual Editing (For Technical Users)

1. **Open `.po` File**
   ```bash
   # Open your language file in a text editor
   nano addon/locale/es/LC_MESSAGES/nvda.po
   ```

2. **Update Header**
   ```po
   "Project-Id-Version: Terminal Access 1.0.32\n"
   "PO-Revision-Date: 2026-02-21 09:00+0000\n"
   "Last-Translator: Your Name <your.email@example.com>\n"
   "Language-Team: Spanish\n"
   "Language: es\n"
   ```

3. **Translate Strings**
   ```po
   #. Translators: Description for reading previous line
   msgid "Read previous line in terminal"
   msgstr "Leer línea anterior en la terminal"
   ```

4. **Format Placeholders**
   - Keep placeholders like `{name}`, `{count}`, `{row}`, etc.
   - Example:
   ```po
   msgid "Found {count} matches"
   msgstr "Se encontraron {count} coincidencias"
   ```

5. **Validate Syntax**
   ```bash
   msgfmt --check addon/locale/es/LC_MESSAGES/nvda.po
   ```

## Translation Guidelines

### General Rules

1. **Consistency**
   - Use consistent terminology throughout the translation
   - Follow NVDA's standard translations for common terms
   - Reference: NVDA's own translation glossary

2. **Placeholders**
   - **NEVER** translate placeholders like `{name}`, `{count}`, `{row}`, `{col}`
   - Keep them exactly as they appear in the English text
   - Example:
     - ✅ CORRECT: `"Fila {row}, columna {col}"`
     - ❌ WRONG: `"Fila {fila}, columna {columna}"`

3. **Keyboard Shortcuts**
   - Keep keyboard shortcut references in English
   - Example: `NVDA+Alt+U` remains `NVDA+Alt+U`

4. **Punctuation**
   - Follow your language's punctuation rules
   - Keep punctuation at the end of sentences if present

5. **Context**
   - Read translator comments (lines starting with `#.`)
   - Context helps ensure accurate translations

### Terminology Guide

| English | Spanish | French | German | Portuguese |
|---------|---------|--------|--------|------------|
| Terminal | Terminal | Terminal | Terminal | Terminal |
| Line | Línea | Ligne | Zeile | Linha |
| Column | Columna | Colonne | Spalte | Coluna |
| Bookmark | Marcador | Signet | Lesezeichen | Marcador |
| Command | Comando | Commande | Befehl | Comando |
| History | Historial | Historique | Verlauf | Histórico |
| Search | Buscar | Rechercher | Suchen | Pesquisar |
| Navigate | Navegar | Naviguer | Navigieren | Navegar |

**Note:** Add entries as you translate. Maintain consistency across all strings.

## Priority Strings

When starting a new translation, focus on these high-priority strings first:

### Critical (User-Facing Messages)
1. Add-on summary and description
2. Gesture descriptions (shown in Input Gestures dialog)
3. Status messages (quiet mode, bookmarks, search results)
4. Error messages

### Important (Less Frequent)
5. Dialog titles and prompts
6. Settings labels
7. Help text

### Low Priority
8. Debug messages
9. Advanced feature descriptions

## Testing Your Translation

### 1. Build the Add-on

```bash
# In the repository root
scons

# This generates addon/locale/<lang>/LC_MESSAGES/nvda.mo from your .po file
```

### 2. Install in NVDA

```bash
# The build process creates terminalAccess-1.0.32.nvda-addon
# Install it in NVDA: NVDA Menu → Tools → Manage Add-ons → Install
```

### 3. Change NVDA Language

```bash
# NVDA Menu → Preferences → General Settings → Language
# Select your language
# Restart NVDA
```

### 4. Test Terminal Access Features

- Open a terminal application
- Test all gestures and features
- Verify messages are displayed correctly
- Check for:
  - Truncated text
  - Incorrect placeholders
  - Missing translations (falls back to English)
  - Cultural appropriateness

## Translation Status

### Supported Languages

| Language | Code | Status | Completeness | Maintainer |
|----------|------|--------|--------------|------------|
| English | en | Native | 100% | Terminal Access Team |
| Spanish | es | In Progress | 0% | Open |
| French | fr | In Progress | 0% | Open |
| German | de | In Progress | 0% | Open |
| Portuguese | pt | In Progress | 0% | Open |
| Chinese (Simplified) | zh_CN | In Progress | 0% | Open |
| Chinese (Traditional) | zh_TW | In Progress | 0% | Open |
| Japanese | ja | In Progress | 0% | Open |
| Russian | ru | In Progress | 0% | Open |

**Want to become a maintainer?** Contact us via GitHub issues!

## Adding a New Language

If your language is not listed above:

1. **Create Directory Structure**
   ```bash
   mkdir -p addon/locale/<lang_code>/LC_MESSAGES
   ```

2. **Copy Template**
   ```bash
   cp addon/locale/tdsr.pot addon/locale/<lang_code>/LC_MESSAGES/nvda.po
   ```

3. **Update Header**
   - Edit the `.po` file header with language information
   - See "Method 2: Manual Editing" above

4. **Translate**
   - Start translating strings using Poedit or text editor

5. **Submit**
   - Create a pull request with your new language

## Common Issues and Solutions

### Issue: Translation Not Showing in NVDA

**Causes:**
- NVDA language setting doesn't match `.po` file language code
- `.mo` file not compiled (run `scons` to compile)
- Translation string is empty (falls back to English)

**Solution:**
1. Verify NVDA language: `NVDA Menu → Preferences → General Settings`
2. Rebuild add-on: `scons`
3. Check for compilation errors: `msgfmt --check <file>.po`

### Issue: Placeholders Not Working

**Cause:** Translated placeholders (e.g., `{count}` → `{cantidad}`)

**Solution:** Keep placeholders in English:
```po
msgid "Found {count} matches"
msgstr "Se encontraron {count} coincidencias"  # {count} stays as-is
```

### Issue: Special Characters Display Incorrectly

**Cause:** Incorrect file encoding

**Solution:**
- Ensure `.po` file is saved as UTF-8
- Check header: `"Content-Type: text/plain; charset=UTF-8\n"`

## Translation Tools

### Recommended Tools

1. **Poedit** (https://poedit.net/)
   - User-friendly GUI
   - Translation memory
   - Syntax checking
   - Available on all platforms

2. **GTranslator** (https://wiki.gnome.org/Apps/Gtranslator)
   - GNOME translation editor
   - Linux only
   - Integration with GNOME ecosystem

3. **Lokalize** (https://apps.kde.org/lokalize/)
   - KDE translation tool
   - Linux only
   - Advanced features for translators

4. **Text Editor** (VS Code, Sublime, Notepad++)
   - For quick edits
   - Install gettext syntax highlighting plugin
   - Manual but full control

### Online Resources

- **NVDA Translation Guide**: https://github.com/nvaccess/nvda/wiki/Translating
- **Gettext Manual**: https://www.gnu.org/software/gettext/manual/gettext.html
- **Python Format Strings**: https://docs.python.org/3/library/string.html#formatstrings

## Contributing

### Ways to Contribute

1. **Translate Strings**
   - Choose an incomplete language
   - Translate untranslated strings
   - Submit via pull request

2. **Review Translations**
   - Check existing translations for accuracy
   - Suggest improvements
   - Report issues via GitHub

3. **Maintain a Language**
   - Commit to keeping a language up-to-date
   - Review new strings as they're added
   - Act as point of contact for that language

4. **Document Terminology**
   - Add entries to the Terminology Guide above
   - Create language-specific glossaries
   - Share translation best practices

### Submission Process

1. **Fork Repository**
   ```bash
   # Fork on GitHub, then:
   git clone https://github.com/<your-username>/Terminal-Access-for-NVDA.git
   ```

2. **Create Branch**
   ```bash
   git checkout -b translation-es
   ```

3. **Make Changes**
   - Translate strings in your `.po` file
   - Test by building and installing

4. **Commit Changes**
   ```bash
   git add addon/locale/es/LC_MESSAGES/nvda.po
   git commit -m "Add Spanish translation for v1.0.32"
   ```

5. **Push and Create PR**
   ```bash
   git push origin translation-es
   # Create Pull Request on GitHub
   ```

6. **PR Review**
   - Maintainers will review your translation
   - May ask for changes or clarifications
   - Once approved, your translation will be merged

## Getting Help

### Support Channels

- **GitHub Issues**: https://github.com/PratikP1/Terminal-Access-for-NVDA/issues
  - For bugs, questions, or suggestions

- **GitHub Discussions**: https://github.com/PratikP1/Terminal-Access-for-NVDA/discussions
  - For general translation questions
  - To coordinate with other translators

- **NVDA Community**: https://www.nvaccess.org/community/
  - For NVDA-specific translation questions

## Credits

Translations are made possible by our community contributors. Thank you to all translators who make Terminal Access accessible to users worldwide!

## License

All translations are distributed under the same license as Terminal Access for NVDA (GPL v2). By contributing translations, you agree to license your work under this license.

---

**Thank you for contributing to Terminal Access for NVDA!**

For questions or assistance, please open an issue on GitHub or contact the maintainers.
