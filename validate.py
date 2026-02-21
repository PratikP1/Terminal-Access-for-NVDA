#!/usr/bin/env python3
"""
Validation script for Terminal Access for NVDA add-on.

This script performs basic checks on the add-on before building or releasing.
Usage: python validate.py
"""

import os
import sys
from pathlib import Path

def check_file_exists(filepath, description):
	"""Check if a required file exists."""
	if os.path.exists(filepath):
		print(f"[OK] {description}: {filepath}")
		return True
	else:
		print(f"[FAIL] {description} MISSING: {filepath}")
		return False

def check_manifest():
	"""Validate manifest.ini file."""
	print("\n=== Checking manifest.ini ===")

	if not os.path.exists("addon/manifest.ini"):
		print("[FAIL] manifest.ini not found!")
		return False

	# NVDA manifest is a flat key=value file (no section headers).
	# Parse it manually to match how NVDA's ConfigObj-based parser reads it.
	manifest = {}
	with open("addon/manifest.ini", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith("#"):
				continue
			if "=" in line:
				key, _, value = line.partition("=")
				manifest[key.strip()] = value.strip().strip('"')

	required_fields = ["name", "summary", "version", "author", "minimumNVDAVersion"]

	all_present = True
	for key in required_fields:
		if key in manifest:
			print(f"[OK] {key} = {manifest[key]}")
		else:
			print(f"[FAIL] {key} MISSING")
			all_present = False

	return all_present

def check_python_syntax():
	"""Check Python files for syntax errors."""
	print("\n=== Checking Python syntax ===")
	
	python_files = list(Path("addon").rglob("*.py"))
	python_files.append(Path("buildVars.py"))
	python_files.append(Path("build.py"))
	
	all_valid = True
	for py_file in python_files:
		try:
			with open(py_file, 'r', encoding='utf-8') as f:
				compile(f.read(), str(py_file), 'exec')
			print(f"[OK] {py_file}")
		except SyntaxError as e:
			print(f"[FAIL] {py_file}: Syntax error at line {e.lineno}")
			all_valid = False
	
	return all_valid

def check_structure():
	"""Check directory structure."""
	print("\n=== Checking directory structure ===")
	
	required_paths = [
		("addon", "Add-on directory"),
		("addon/globalPlugins", "Global plugins directory"),
		("addon/globalPlugins/terminalAccess.py", "Main plugin file"),
		("addon/doc/en", "English documentation directory"),
		("addon/doc/en/readme.html", "User guide"),
		("addon/manifest.ini", "Manifest file"),
		("buildVars.py", "Build variables"),
	]
	
	all_present = True
	for path, description in required_paths:
		if not check_file_exists(path, description):
			all_present = False
	
	return all_present

def check_documentation():
	"""Check documentation completeness."""
	print("\n=== Checking documentation ===")
	
	docs = [
		"README.md",
		"CHANGELOG.md",
		"INSTALL.md",
		"ROADMAP.md",
		"CONTRIBUTING.md",
		"LICENSE",
	]
	
	all_present = True
	for doc in docs:
		if not check_file_exists(doc, f"Documentation: {doc}"):
			all_present = False
	
	return all_present

def check_user_guide():
	"""Check user guide content."""
	print("\n=== Checking user guide ===")
	
	guide_path = "addon/doc/en/readme.html"
	if not os.path.exists(guide_path):
		print("[FAIL] User guide not found")
		return False
	
	with open(guide_path, 'r', encoding='utf-8') as f:
		content = f.read()
	
	required_sections = [
		"Introduction",
		"Features",
		"Keyboard Commands",
		"Settings",
		"Troubleshooting",
	]
	
	all_present = True
	for section in required_sections:
		if section.lower() in content.lower():
			print(f"[OK] Section found: {section}")
		else:
			print(f"[FAIL] Section missing: {section}")
			all_present = False
	
	return all_present

def main():
	"""Run all validation checks."""
	print("=" * 60)
	print("Terminal Access for NVDA - Validation Script")
	print("=" * 60)
	
	# Change to script directory
	os.chdir(os.path.dirname(os.path.abspath(__file__)))
	
	checks = [
		("Directory Structure", check_structure),
		("Manifest", check_manifest),
		("Python Syntax", check_python_syntax),
		("Documentation", check_documentation),
		("User Guide", check_user_guide),
	]
	
	results = []
	for name, check_func in checks:
		try:
			result = check_func()
			results.append((name, result))
		except Exception as e:
			print(f"\n[FAIL] Error running {name} check: {e}")
			results.append((name, False))
	
	# Summary
	print("\n" + "=" * 60)
	print("VALIDATION SUMMARY")
	print("=" * 60)
	
	all_passed = True
	for name, result in results:
		status = "PASSED" if result else "FAILED"
		symbol = "[OK]" if result else "[FAIL]"
		print(f"{symbol} {name}: {status}")
		if not result:
			all_passed = False
	
	print("=" * 60)
	
	if all_passed:
		print("\n[OK] All checks passed! Add-on is ready for building.")
		return 0
	else:
		print("\n[FAIL] Some checks failed. Please fix the issues before building.")
		return 1

if __name__ == "__main__":
	sys.exit(main())
