"""
Utilities for Apple Music MCP Chatbot.

This package contains integrations with external services (GPT-4o via GitHub
inference endpoint) and utility functions for the music chatbot.
"""

from .gpt_integration import GPTMusicAssistant

__all__ = ["GPTMusicAssistant"]
