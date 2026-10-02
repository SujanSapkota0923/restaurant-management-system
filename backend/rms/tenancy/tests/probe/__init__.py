"""Test-only tenant-owned tables for the isolation harness (change 0004, D6).

Installed only by ``config.settings.test``; local and production settings never
install it (C-18), so its tables exist only in test and round-trip databases.
"""
