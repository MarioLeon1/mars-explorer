"""Optional AI mission assistant (Claude via the Anthropic API).

The assistant only *reads* this app's data through a fixed set of read-only tools. It cannot plan
routes, start downloads, change settings or control anything (integrity rule 6). It is disabled
unless ``ANTHROPIC_API_KEY`` is configured.
"""
