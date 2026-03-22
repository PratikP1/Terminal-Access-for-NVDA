# Terminal Access Documentation

This directory contains all documentation for the Terminal Access for NVDA add-on, organized by audience and purpose.

## Directory Structure

### `user/` - User Documentation
Documentation for end users of the Terminal Access add-on:
- **ADVANCED_USER_GUIDE.md** - Advanced features guide
- **FAQ.md** - Frequently asked questions
- **WSL_TESTING_GUIDE.md** - Guide for using Terminal Access with Windows Subsystem for Linux
- **TRANSLATION_GUIDE.md** - Guide for contributing translations

### `developer/` - Developer Documentation
Technical documentation for developers and contributors:
- **ARCHITECTURE.md** - System architecture and design patterns
- **API_REFERENCE.md** - API documentation
- **ROADMAP.md** - Project roadmap and future plans

### `testing/` - Testing Documentation
Testing procedures and guidelines:
- **TESTING_GUIDE.md** - Automated and manual testing procedures

### `archive/` - Archived Documentation
Historical documentation preserved for reference:
- **FUTURE_ENHANCEMENTS.md** - Enhancement tracking (all items complete)

#### `archive/development/`
Development artifacts from earlier project phases:
- **PHASE1_SPECS.md** - Phase 1 specifications (completed in v1.0.11-1.0.13)
- **PHASE2_SPECS.md** - Phase 2 specifications (completed in v1.0.14-1.0.16)
- **IMPLEMENTATION_v1.0.0.md** - Original implementation summary from v1.0.0
- **REMAINING_WORK_v1.0.14.md** - Work analysis from v1.0.14 (superseded by FUTURE_ENHANCEMENTS.md)

#### `archive/research/`
Research and analysis documents:
- **SPEAKUP_FEATURE_ANALYSIS.md** - Analysis of Speakup features (original inspiration from TDSR project)
- **SPEAKUP_SPECS_REQUIREMENTS.md** - Consolidated specification document
- **API_RESEARCH_COORDINATE_TRACKING.md** - Technical research on coordinate tracking and rectangular selection

#### `archive/implementation/`
Detailed implementation summaries for specific features:
- **CURSOR_TRACKING_IMPLEMENTATION.md** - Cursor tracking implementation details

## Quick Links

### For Users
Start with the [main README](../README.md), then:
1. [QUICKSTART](../QUICKSTART.md) - Get started quickly
2. [INSTALL](../INSTALL.md) - Installation guide
3. [ADVANCED_USER_GUIDE](user/ADVANCED_USER_GUIDE.md) - Learn advanced features
4. [FAQ](user/FAQ.md) - Common questions

### For Developers
Start with [CONTRIBUTING](../CONTRIBUTING.md), then:
1. [ARCHITECTURE](developer/ARCHITECTURE.md) - Understand the system design
2. [API_REFERENCE](developer/API_REFERENCE.md) - API documentation
3. [TESTING_GUIDE](testing/TESTING_GUIDE.md) - Testing procedures
4. [ROADMAP](developer/ROADMAP.md) - Future plans

### For Translators
See [TRANSLATION_GUIDE](user/TRANSLATION_GUIDE.md) for instructions on contributing translations.

## Documentation Organization Principles

1. **User-First**: User documentation is separate from developer documentation
2. **Current vs. Historical**: Active documentation is at the top level; historical artifacts are archived
3. **Single Source of Truth**: Avoid duplication; link to canonical sources
4. **Clear Navigation**: Each document links to related documents
5. **Preservation**: Historical documents are archived, not deleted, for future reference

## Contributing to Documentation

When contributing documentation:
- User-facing docs go in `user/`
- Developer/technical docs go in `developer/`
- Testing-related docs go in `testing/`
- Historical/superseded docs go in `archive/` with version/date notation
- Update README.md in the repository root when adding new documentation
- Keep the CHANGELOG.md updated with documentation changes

## Version History

This documentation structure was established in **v1.0.32** to:
- Reduce root-level clutter (from 23 to 6 markdown files)
- Organize documentation by audience
- Archive historical development artifacts

For the complete version history, see [CHANGELOG.md](../CHANGELOG.md).
