#!/usr/bin/env python3
"""
Simple build script for Terminal Access for NVDA add-on.

This script creates an NVDA add-on package without requiring SCons.
Usage: python build.py [--non-interactive | -y]

Options:
  --non-interactive, -y   Run in non-interactive mode (auto-overwrite)
"""

import os
import sys
import zipfile
from pathlib import Path

# Import build variables
import buildVars

def create_addon(output_file):
	"""
	Create an NVDA add-on bundle.
	
	Args:
		output_file: Path to the output .nvda-addon file
	"""
	print(f"Creating add-on package: {output_file}")
	
	with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as addon_zip:
		# Add all files from addon directory (manifest.ini lives inside addon/)
		addon_path = Path("addon")
		for file_path in addon_path.rglob("*"):
			if file_path.is_file():
				# Skip __pycache__ and .pyc files
				if '__pycache__' in str(file_path) or file_path.suffix == '.pyc':
					continue

				# Calculate archive path (relative to addon directory)
				arc_path = file_path.relative_to(addon_path)

				# Skip the addon/__init__.py file (should not be at root level in the package)
				if str(arc_path) == '__init__.py':
					print(f"  Skipped: {arc_path} (not needed in NVDA addon package)")
					continue

				addon_zip.write(str(file_path), arcname=str(arc_path))
				print(f"  Added: {arc_path}")
	
	print(f"\nAdd-on package created successfully: {output_file}")
	print(f"File size: {os.path.getsize(output_file) / 1024:.2f} KB")

def main():
	"""Main build function."""
	# Get add-on information
	addon_info = buildVars.addon_info
	addon_name = addon_info["addon_name"]
	addon_version = addon_info["addon_version"]
	
	# Define output filename
	output_file = f"{addon_name}-{addon_version}.nvda-addon"
	
	# Check for non-interactive mode
	non_interactive = "--non-interactive" in sys.argv or "-y" in sys.argv
	
	# Check if output file already exists
	if os.path.exists(output_file):
		if non_interactive:
			print(f"\n{output_file} already exists. Overwriting (non-interactive mode)...")
			os.remove(output_file)
		else:
			response = input(f"\n{output_file} already exists. Overwrite? (y/n): ")
			if response.lower() != 'y':
				print("Build cancelled.")
				return 1
			os.remove(output_file)
	
	# Create the add-on
	try:
		create_addon(output_file)
		return 0
	except Exception as e:
		print(f"\nError creating add-on: {e}", file=sys.stderr)
		return 1

if __name__ == "__main__":
	sys.exit(main())
