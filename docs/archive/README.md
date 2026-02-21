# Archived Documentation

This directory contains historical documentation from the Terminal Access for NVDA project. These documents are preserved for reference but have been superseded by current documentation.

## Why Archive Documentation?

Archived documents serve several purposes:
1. **Historical Record** - Preserve the development history and decision-making process
2. **Reference Material** - Provide context for understanding implementation choices
3. **Learning Resource** - Help new contributors understand how the project evolved
4. **Continuity** - Maintain git history and external references

## Archive Structure

### `development/` - Development Artifacts

**Phase Specifications** (Completed in v1.0.11-1.0.16):
- **PHASE1_SPECS.md** - Phase 1 specifications
  - Status: ✅ Completed in v1.0.11-1.0.13
  - Features: Continuous Reading, Screen Edge Navigation, Reading Modes
  - Superseded by: CHANGELOG.md entries for v1.0.11-1.0.13

- **PHASE2_SPECS.md** - Phase 2 specifications
  - Status: ✅ Completed in v1.0.14-1.0.16
  - Features: Punctuation Levels, Attribute Reading, Indentation Detection
  - Superseded by: CHANGELOG.md entries for v1.0.14-1.0.16

**Implementation Summaries**:
- **IMPLEMENTATION_v1.0.0.md** - Original implementation summary
  - Version: v1.0.0 (February 2024)
  - Status: ✅ Initial release complete
  - Superseded by: CHANGELOG.md comprehensive history

**Work Analysis**:
- **REMAINING_WORK_v1.0.14.md** - Work remaining as of v1.0.14
  - Version: v1.0.14 (~70% complete)
  - Status: ✅ Work completed in subsequent versions
  - Superseded by: FUTURE_ENHANCEMENTS.md (v8.0, 100% complete)

### `research/` - Research Documents

**Feature Analysis**:
- **SPEAKUP_FEATURE_ANALYSIS.md** - Analysis of Speakup screen reader features
  - Purpose: Identify features to adapt from Speakup for terminal use
  - Status: ✅ Research complete, features implemented
  - Impact: Inspired cursor tracking modes, screen windowing, attribute reading

- **SPEAKUP_SPECS_REQUIREMENTS.md** - Consolidated requirements document
  - Purpose: Comprehensive specification combining multiple sources
  - Status: ✅ Requirements implemented across v1.0.0-1.0.32
  - Superseded by: CHANGELOG.md and FUTURE_ENHANCEMENTS.md

**Technical Research**:
- **API_RESEARCH_COORDINATE_TRACKING.md** - Coordinate tracking and rectangular selection research
  - Size: 1,408 lines, 42KB
  - Purpose: Deep dive into NVDA TextInfo API for position tracking
  - Status: ✅ Research complete, features implemented
  - Implementation: Rectangular selection (v1.0.13), Enhanced windowing (v1.0.13-1.0.16)

### `implementation/` - Feature Implementation Summaries

- **CURSOR_TRACKING_IMPLEMENTATION.md** - Cursor tracking modes implementation
  - Features: Multiple tracking modes (Standard, Highlight, Window, Off)
  - Status: ✅ Implemented in v1.0.13-1.0.16
  - Superseded by: ARCHITECTURE.md, API_REFERENCE.md, and relevant CHANGELOG.md entries

## Using Archived Documentation

### When to Consult Archives

**DO consult archives when:**
- Understanding the historical development of a feature
- Researching why certain design decisions were made
- Looking for detailed technical research on NVDA APIs
- Wanting to understand the project's evolution

**DON'T consult archives when:**
- Looking for current feature documentation (use main docs)
- Seeking API reference (use docs/developer/API_REFERENCE.md)
- Following development guides (use CONTRIBUTING.md)
- Looking for current project status (use FUTURE_ENHANCEMENTS.md)

### Cross-References

Most archived documents reference other documents. When following links:
- Check if the referenced document is also archived
- If links are broken, search in the current documentation structure
- Refer to git history for full context: `git log --follow <filename>`

## Restoration Policy

Documents in this archive are **read-only** and should not be updated unless:
1. Fixing critical factual errors
2. Adding archival notices or cross-references
3. Updating links to point to archived locations

For questions or clarification about archived documents, please open a GitHub issue.

## Timeline

- **February 2024**: v1.0.0 - Initial release (IMPLEMENTATION_v1.0.0.md)
- **v1.0.11-1.0.13**: Phase 1 features complete (PHASE1_SPECS.md)
- **v1.0.14-1.0.16**: Phase 2 features complete (PHASE2_SPECS.md)
- **v1.0.17-1.0.32**: Advanced features and refinements
- **v1.0.32**: Documentation consolidation - these documents archived

## See Also

- [CHANGELOG.md](../../CHANGELOG.md) - Complete version history from v1.0.0 to current
- [FUTURE_ENHANCEMENTS.md](../developer/FUTURE_ENHANCEMENTS.md) - Current feature tracking (100% complete)
- [ARCHITECTURE.md](../developer/ARCHITECTURE.md) - Current system architecture
- [API_REFERENCE.md](../developer/API_REFERENCE.md) - Current API documentation
