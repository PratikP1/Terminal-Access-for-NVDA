"""Gesture conflict detection for Terminal Access.

Detects when Terminal Access gestures conflict with other NVDA addons
and provides a human-readable report.
"""


class GestureConflictDetector:
	"""Detect gesture conflicts between Terminal Access and other NVDA plugins."""

	def detect_conflicts(self, our_gestures, other_plugins,
						 our_class_name="GlobalPlugin", excluded_gestures=None):
		"""Find gestures that conflict with other loaded plugins.

		Args:
			our_gestures: Dict of gesture -> script_name for Terminal Access.
			other_plugins: List of other GlobalPlugin instances.
			our_class_name: Our plugin's class name (to skip self).
			excluded_gestures: Set of gestures the user has already unbound.

		Returns:
			List of conflict dicts with keys: gesture, our_script,
			other_plugin, other_script.
		"""
		if excluded_gestures is None:
			excluded_gestures = set()

		conflicts = []
		for plugin in other_plugins:
			# Skip ourselves
			if plugin.__class__.__name__ == our_class_name:
				continue

			# Get the other plugin's gestures
			other_gestures = self._get_plugin_gestures(plugin)
			if not other_gestures:
				continue

			plugin_name = plugin.__class__.__name__

			for gesture, our_script in our_gestures.items():
				if gesture in excluded_gestures:
					continue
				if gesture in other_gestures:
					conflicts.append({
						"gesture": gesture,
						"our_script": our_script,
						"other_plugin": plugin_name,
						"other_script": other_gestures[gesture],
					})

		return conflicts

	def _get_plugin_gestures(self, plugin):
		"""Extract gesture map from a plugin, handling missing attributes."""
		# Try _gestureMap (instance-level bindings)
		gestures = getattr(plugin, '_gestureMap', None)
		if gestures:
			return dict(gestures)

		# Try __gestures (class-level dict)
		cls = plugin.__class__
		for attr in dir(cls):
			if attr.endswith('__gestures'):
				val = getattr(cls, attr, None)
				if isinstance(val, dict):
					return dict(val)

		return {}

	def format_report(self, conflicts):
		"""Format conflicts into a readable string.

		Args:
			conflicts: List of conflict dicts from detect_conflicts.

		Returns:
			Formatted string, or empty string if no conflicts.
		"""
		if not conflicts:
			return ""

		lines = []
		for c in conflicts:
			gesture_display = c["gesture"].replace("kb:", "").upper()
			lines.append(
				f"{gesture_display}: {c['our_script']} conflicts with "
				f"{c['other_plugin']}"
			)
		return "\n".join(lines)
