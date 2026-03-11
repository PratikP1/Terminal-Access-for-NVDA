#!/usr/bin/env python3
"""
Extract translatable strings, update .po files, and auto-translate via Google Translate.

Usage:
    python scripts/translate.py                # Extract + merge + translate all
    python scripts/translate.py --extract      # Only regenerate .pot and merge .po files
    python scripts/translate.py --lang es fr   # Translate only specific languages
"""
import argparse
import os
import re
import sys
import time

import polib
from deep_translator import GoogleTranslator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(PROJECT_ROOT, "addon")
LOCALE_DIR = os.path.join(ADDON_DIR, "locale")
POT_PATH = os.path.join(ADDON_DIR, "locale", "terminalAccess.pot")
SOURCE_FILES = [
    os.path.join(ADDON_DIR, "globalPlugins", "terminalAccess.py"),
    os.path.join(PROJECT_ROOT, "buildVars.py"),
]

# Language codes → Google Translate codes
LANGUAGES = {
    "de": "de",
    "es": "es",
    "fr": "fr",
    "ja": "ja",
    "pt": "pt",
    "ru": "ru",
    "zh_CN": "zh-CN",
    "zh_TW": "zh-TW",
}

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_strings(filepath: str) -> list[tuple[str, int, str]]:
    """Extract translatable _() strings from a Python source file.

    Returns list of (string, line_number, translator_comment).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    results = []
    # Regex for single-line _("...") calls
    single_pat = re.compile(r'''_\(\s*"((?:[^"\\]|\\.)*)"\s*\)''')
    # Regex for single-line _("..." \n "...") continuation
    concat_start = re.compile(r'''_\(\s*"((?:[^"\\]|\\.)*)"\s*$''')
    concat_cont = re.compile(r'''^\s*"((?:[^"\\]|\\.)*)"\s*\)''')
    # Regex for triple-quoted _() in buildVars
    triple_pat = re.compile(r'_\(\s*"""(.*?)"""\s*\)', re.DOTALL)
    # Regex for multi-line _(\n"..."\n) calls
    multiline_start = re.compile(r'''_\(\s*$''')

    source = "".join(lines)

    # First pass: triple-quoted strings (buildVars)
    for m in triple_pat.finditer(source):
        s = m.group(1).strip()
        line_no = source[:m.start()].count("\n") + 1
        comment = _find_translator_comment(lines, line_no)
        results.append((s, line_no, comment))

    # Second pass: line-by-line for regular _() calls
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for single-line _("...")
        for m in single_pat.finditer(line):
            s = m.group(1)
            if s:
                comment = _find_translator_comment(lines, i + 1)
                results.append((s, i + 1, comment))

        # Check for _("...\n"...\n) multi-line concatenation
        cm = concat_start.search(line)
        if cm and not single_pat.search(line):
            parts = [cm.group(1)]
            j = i + 1
            while j < len(lines):
                cont_line = lines[j]
                # Continuation "..."
                cont_m = re.match(r'''^\s*"((?:[^"\\]|\\.)*)"\s*$''', cont_line)
                end_m = re.match(r'''^\s*"((?:[^"\\]|\\.)*)"\s*\)''', cont_line)
                if end_m:
                    parts.append(end_m.group(1))
                    break
                elif cont_m:
                    parts.append(cont_m.group(1))
                else:
                    break
                j += 1
            s = "".join(parts)
            if s:
                comment = _find_translator_comment(lines, i + 1)
                # Avoid duplicates from single_pat
                if not any(r[0] == s for r in results):
                    results.append((s, i + 1, comment))

        # Multi-line _(\n"..."\n)
        if multiline_start.search(line):
            j = i + 1
            parts = []
            while j < len(lines):
                nl = lines[j]
                nm = re.match(r'''^\s*"((?:[^"\\]|\\.)*)"\s*\)''', nl)
                nm2 = re.match(r'''^\s*"((?:[^"\\]|\\.)*)"\s*$''', nl)
                if nm:
                    parts.append(nm.group(1))
                    break
                elif nm2:
                    parts.append(nm2.group(1))
                else:
                    break
                j += 1
            s = "".join(parts)
            if s:
                comment = _find_translator_comment(lines, i + 1)
                if not any(r[0] == s for r in results):
                    results.append((s, i + 1, comment))

        i += 1

    return results


def _find_translator_comment(lines: list[str], line_no: int) -> str:
    """Look backwards from line_no for a '# Translators:' comment."""
    idx = line_no - 2  # line_no is 1-based, check line above
    while idx >= 0 and idx >= line_no - 5:
        stripped = lines[idx].strip()
        if stripped.startswith("# Translators:"):
            return stripped.replace("# Translators:", "").strip()
        if stripped and not stripped.startswith("#"):
            break
        idx -= 1
    return ""


def generate_pot() -> polib.POFile:
    """Extract all translatable strings and create a .pot file."""
    pot = polib.POFile()
    pot.metadata = {
        "Project-Id-Version": "Terminal Access for NVDA",
        "Report-Msgid-Bugs-To": "https://github.com/PratikP1/Terminal-Access-for-NVDA/issues",
        "POT-Creation-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "PO-Revision-Date": "YEAR-MO-DA HO:MI+ZONE",
        "Last-Translator": "",
        "Language-Team": "",
        "Language": "",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }

    seen = set()
    for filepath in SOURCE_FILES:
        if not os.path.exists(filepath):
            print(f"  Warning: {filepath} not found, skipping")
            continue
        relpath = os.path.relpath(filepath, PROJECT_ROOT)
        strings = extract_strings(filepath)
        for s, line_no, comment in strings:
            if s in seen:
                continue
            seen.add(s)
            entry = polib.POEntry(
                msgid=s,
                msgstr="",
                occurrences=[(relpath.replace("\\", "/"), str(line_no))],
            )
            if comment:
                entry.tcomment = comment
            # Detect python-format strings
            if re.search(r"\{[^}]*\}", s):
                entry.flags.append("python-brace-format")
            pot.append(entry)

    pot.save(POT_PATH)
    return pot


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_po(lang_code: str, pot: polib.POFile) -> polib.POFile:
    """Update a .po file to match the .pot, preserving existing translations."""
    po_path = os.path.join(LOCALE_DIR, lang_code, "LC_MESSAGES", "nvda.po")

    if os.path.exists(po_path):
        po = polib.pofile(po_path)
    else:
        os.makedirs(os.path.dirname(po_path), exist_ok=True)
        po = polib.POFile()

    # Update metadata
    po.metadata = {
        "Project-Id-Version": "Terminal Access for NVDA",
        "Report-Msgid-Bugs-To": "https://github.com/PratikP1/Terminal-Access-for-NVDA/issues",
        "POT-Creation-Date": pot.metadata.get("POT-Creation-Date", ""),
        "PO-Revision-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "Last-Translator": "Auto-translated",
        "Language-Team": lang_code,
        "Language": lang_code,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }

    # Build lookup of existing translations
    existing = {e.msgid: e.msgstr for e in po if e.msgstr}

    # Rebuild from pot
    po.clear()  # polib: remove all entries
    # Actually polib doesn't have clear(), let's rebuild
    new_po = polib.POFile()
    new_po.metadata = po.metadata

    for pot_entry in pot:
        entry = polib.POEntry(
            msgid=pot_entry.msgid,
            msgstr=existing.get(pot_entry.msgid, ""),
            occurrences=pot_entry.occurrences,
            tcomment=pot_entry.tcomment,
            flags=list(pot_entry.flags),
        )
        new_po.append(entry)

    new_po.save(po_path)
    return new_po


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def translate_po(lang_code: str, google_lang: str) -> tuple[int, int]:
    """Translate empty msgstr entries using Google Translate.

    Returns (translated_count, total_count).
    """
    po_path = os.path.join(LOCALE_DIR, lang_code, "LC_MESSAGES", "nvda.po")
    po = polib.pofile(po_path)

    translator = GoogleTranslator(source="en", target=google_lang)

    untranslated = [e for e in po if not e.msgstr]
    total = len(po)
    count = 0

    for entry in untranslated:
        text = entry.msgid

        # Protect python-brace-format placeholders
        placeholders = {}
        for i, m in enumerate(re.finditer(r"\{[^}]*\}", text)):
            token = f"__PH{i}__"
            placeholders[token] = m.group(0)
            text = text.replace(m.group(0), token, 1)

        try:
            translated = translator.translate(text)
            if not translated:
                continue

            # Restore placeholders
            for token, original in placeholders.items():
                translated = translated.replace(token, original)

            entry.msgstr = translated
            if "fuzzy" not in entry.flags:
                entry.flags.append("fuzzy")
            count += 1

            # Rate limiting — Google Translate free tier
            time.sleep(0.3)

        except Exception as e:
            print(f"    Error translating '{entry.msgid[:40]}...': {e}")
            continue

    po.save(po_path)
    return count, total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage translations for Terminal Access")
    parser.add_argument("--extract", action="store_true", help="Only extract .pot and merge .po (no translation)")
    parser.add_argument("--lang", nargs="*", help="Only translate specific languages (e.g., es fr)")
    args = parser.parse_args()

    # Step 1: Generate .pot
    print("Extracting translatable strings...")
    pot = generate_pot()
    print(f"  {len(pot)} strings -> {POT_PATH}")

    # Step 2: Merge all .po files
    langs = args.lang if args.lang else list(LANGUAGES.keys())
    for lang in langs:
        if lang not in LANGUAGES:
            print(f"  Unknown language: {lang}, skipping")
            continue
        po = merge_po(lang, pot)
        untranslated = len([e for e in po if not e.msgstr])
        print(f"  {lang}: {len(po)} strings, {untranslated} untranslated")

    if args.extract:
        print("Done (extract only).")
        return

    # Step 3: Translate
    print("\nTranslating...")
    for lang in langs:
        if lang not in LANGUAGES:
            continue
        google_lang = LANGUAGES[lang]
        print(f"  {lang} ({google_lang})...", end=" ", flush=True)
        translated, total = translate_po(lang, google_lang)
        print(f"{translated}/{total} translated")

    print("\nDone. All translations marked as 'fuzzy' for human review.")


if __name__ == "__main__":
    main()
