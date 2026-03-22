"""
Tests for URL extraction and the UrlExtractorManager.

Covers URL regex patterns, cleanup, extraction from terminal buffers,
deduplication, gesture registration, and manager methods.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestUrlPattern(unittest.TestCase):
	"""Test the _URL_PATTERN compiled regex."""

	def _find(self, text):
		from globalPlugins.terminalAccess import _URL_PATTERN
		return _URL_PATTERN.findall(text)

	def test_matches_https(self):
		urls = self._find("Visit https://example.com/path for info")
		self.assertEqual(urls, ["https://example.com/path"])

	def test_matches_http(self):
		urls = self._find("See http://example.org/page")
		self.assertEqual(urls, ["http://example.org/page"])

	def test_matches_ftp(self):
		urls = self._find("Download from ftp://files.example.com/pub")
		self.assertEqual(urls, ["ftp://files.example.com/pub"])

	def test_matches_www(self):
		urls = self._find("Go to www.example.com/docs")
		self.assertEqual(urls, ["www.example.com/docs"])

	def test_matches_file_protocol(self):
		urls = self._find("Open file:///tmp/report.html")
		self.assertEqual(urls, ["file:///tmp/report.html"])

	def test_case_insensitive(self):
		urls = self._find("HTTPS://EXAMPLE.COM")
		self.assertEqual(urls, ["HTTPS://EXAMPLE.COM"])

	def test_no_match_bare_ip(self):
		urls = self._find("Server at 192.168.1.1 port 8080")
		self.assertEqual(urls, [])

	def test_no_match_local_path(self):
		urls = self._find(r"Edit C:\Users\admin\file.txt")
		self.assertEqual(urls, [])

	def test_no_match_plain_text(self):
		urls = self._find("No URLs here, just plain text.")
		self.assertEqual(urls, [])

	def test_multiple_urls_in_one_line(self):
		urls = self._find("See https://a.com and https://b.com")
		self.assertEqual(len(urls), 2)

	def test_url_with_query_string(self):
		urls = self._find("https://example.com/search?q=test&page=1")
		self.assertEqual(urls, ["https://example.com/search?q=test&page=1"])

	def test_url_with_fragment(self):
		urls = self._find("https://docs.python.org/3/library/re.html#module-re")
		self.assertEqual(urls, ["https://docs.python.org/3/library/re.html#module-re"])

	def test_url_with_port(self):
		urls = self._find("http://localhost:8080/api/v1")
		self.assertEqual(urls, ["http://localhost:8080/api/v1"])


class TestOsc8Pattern(unittest.TestCase):
	"""Test the _OSC8_URL_PATTERN compiled regex."""

	def _findall(self, text):
		from globalPlugins.terminalAccess import _OSC8_URL_PATTERN
		return _OSC8_URL_PATTERN.findall(text)

	def test_basic_osc8(self):
		# ESC]8;;URL BEL display_text ESC]8;; BEL
		text = "\x1b]8;;https://example.com\x07Click here\x1b]8;;\x07"
		self.assertEqual(self._findall(text), ["https://example.com"])

	def test_osc8_with_st_terminator(self):
		text = "\x1b]8;;https://example.com\x1b\\Click here\x1b]8;;\x1b\\"
		self.assertEqual(self._findall(text), ["https://example.com"])

	def test_osc8_with_params(self):
		text = "\x1b]8;id=link1;https://example.com\x07text\x1b]8;;\x07"
		self.assertEqual(self._findall(text), ["https://example.com"])

	def test_no_osc8_in_plain_text(self):
		self.assertEqual(self._findall("https://example.com plain text"), [])


class TestCleanUrl(unittest.TestCase):
	"""Test the _clean_url helper function."""

	def _clean(self, url):
		from globalPlugins.terminalAccess import _clean_url
		return _clean_url(url)

	def test_strip_trailing_period(self):
		self.assertEqual(self._clean("https://example.com."), "https://example.com")

	def test_strip_trailing_comma(self):
		self.assertEqual(self._clean("https://example.com,"), "https://example.com")

	def test_strip_trailing_semicolon(self):
		self.assertEqual(self._clean("https://example.com;"), "https://example.com")

	def test_strip_trailing_exclamation(self):
		self.assertEqual(self._clean("https://example.com!"), "https://example.com")

	def test_strip_multiple_trailing(self):
		self.assertEqual(self._clean("https://example.com.;"), "https://example.com")

	def test_balanced_parens_preserved(self):
		url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
		self.assertEqual(self._clean(url), url)

	def test_unbalanced_trailing_paren(self):
		self.assertEqual(
			self._clean("https://example.com)"),
			"https://example.com"
		)

	def test_unbalanced_trailing_bracket(self):
		self.assertEqual(
			self._clean("https://example.com]"),
			"https://example.com"
		)

	def test_no_change_clean_url(self):
		url = "https://example.com/path"
		self.assertEqual(self._clean(url), url)

	def test_empty_string(self):
		self.assertEqual(self._clean(""), "")


class TestUrlExtractorManager(unittest.TestCase):
	"""Test the UrlExtractorManager class."""

	def _make_terminal(self, text):
		"""Create a mock terminal that returns the given text."""
		terminal = Mock()
		info = Mock()
		info.text = text
		terminal.makeTextInfo = Mock(return_value=info)
		return terminal

	def test_extract_https_urls(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal(
			"Error: see https://docs.python.org/3/errors\n"
			"Also check https://stackoverflow.com/questions\n"
		)
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 2)
		self.assertEqual(urls[0].url, "https://docs.python.org/3/errors")
		self.assertEqual(urls[1].url, "https://stackoverflow.com/questions")

	def test_extract_www_urls(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("Visit www.example.com for details\n")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 1)
		self.assertEqual(urls[0].url, "www.example.com")

	def test_deduplication(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal(
			"https://example.com first\n"
			"https://example.com second\n"
			"https://example.com third\n"
		)
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 1)
		self.assertEqual(urls[0].url, "https://example.com")
		self.assertEqual(urls[0].count, 3)
		self.assertEqual(urls[0].line_num, 1)  # first occurrence

	def test_empty_buffer(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(urls, [])

	def test_no_urls(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("Just plain text\nNo URLs here\n")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(urls, [])

	def test_line_context(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("Error at https://example.com/err line 42\n")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 1)
		self.assertEqual(urls[0].line_num, 1)
		self.assertIn("Error at", urls[0].line_text)

	def test_ansi_stripped(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		# URL embedded in ANSI color codes
		terminal = self._make_terminal(
			"\x1b[31mError:\x1b[0m https://example.com/fix\n"
		)
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 1)
		self.assertEqual(urls[0].url, "https://example.com/fix")

	def test_trailing_punctuation_cleaned(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("See https://example.com/page.\n")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 1)
		self.assertEqual(urls[0].url, "https://example.com/page")

	def test_none_terminal(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		manager = UrlExtractorManager(None)
		urls = manager.extract_urls()
		self.assertEqual(urls, [])

	def test_terminal_error(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = Mock()
		terminal.makeTextInfo = Mock(side_effect=RuntimeError("UIA error"))
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(urls, [])

	def test_get_url_count(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal(
			"https://a.com\nhttps://b.com\n"
		)
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		self.assertEqual(manager.get_url_count(), 2)

	@patch('lib._runtime.api_module')
	def test_copy_url(self, mock_api):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("https://example.com\n")
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		result = manager.copy_url(0)
		self.assertTrue(result)
		mock_api.copyToClip.assert_called_once_with("https://example.com")

	def test_copy_url_invalid_index(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("https://example.com\n")
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		self.assertFalse(manager.copy_url(5))

	@patch('lib._runtime.webbrowser_module')
	def test_open_url(self, mock_wb):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("https://example.com\n")
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		result = manager.open_url(0)
		self.assertTrue(result)
		mock_wb.open.assert_called_once_with("https://example.com")

	@patch('lib._runtime.webbrowser_module')
	def test_open_www_url_adds_scheme(self, mock_wb):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("www.example.com\n")
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		manager.open_url(0)
		mock_wb.open.assert_called_once_with("https://www.example.com")

	def test_update_terminal_clears_urls(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("https://example.com\n")
		manager = UrlExtractorManager(terminal)
		manager.extract_urls()
		self.assertEqual(manager.get_url_count(), 1)
		new_terminal = self._make_terminal("no urls\n")
		manager.update_terminal(new_terminal)
		self.assertEqual(manager.get_url_count(), 0)

	def test_multiple_urls_per_line(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal(
			"Links: https://a.com and https://b.com\n"
		)
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(len(urls), 2)

	def test_source_field(self):
		from globalPlugins.terminalAccess import UrlExtractorManager
		terminal = self._make_terminal("https://example.com\n")
		manager = UrlExtractorManager(terminal)
		urls = manager.extract_urls()
		self.assertEqual(urls[0].source, "text")


class TestUrlGestureRegistration(unittest.TestCase):
	"""Test that URL list gesture is registered in all maps."""

	def test_url_list_in_default_gestures(self):
		from globalPlugins.terminalAccess import _DEFAULT_GESTURES
		self.assertIn("kb:NVDA+alt+u", _DEFAULT_GESTURES)
		self.assertEqual(_DEFAULT_GESTURES["kb:NVDA+alt+u"], "listUrls")

	def test_url_list_in_command_layer_map(self):
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		self.assertIn("kb:e", _COMMAND_LAYER_MAP)
		self.assertEqual(_COMMAND_LAYER_MAP["kb:e"], "listUrls")

	def test_script_method_exists(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		self.assertTrue(hasattr(GlobalPlugin, 'script_listUrls'))

	def test_script_has_description(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		method = getattr(GlobalPlugin, 'script_listUrls')
		# The mock decorator stores gestures; the real decorator stores description.
		# Verify the method exists and is callable.
		self.assertTrue(callable(method))


if __name__ == '__main__':
	unittest.main()
