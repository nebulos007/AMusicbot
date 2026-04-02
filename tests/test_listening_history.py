"""
Unit tests for listening history management.

Tests persistent storage, play/skip tracking, and statistics.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from listening_history import ListeningHistory


class TestListeningHistory:
    """Test suite for ListeningHistory."""
    
    @pytest.fixture
    def temp_history_file(self):
        """Create a temporary history file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def history(self, temp_history_file):
        """Create a history instance with temp file."""
        return ListeningHistory(temp_history_file)
    
    def test_initialization(self, history):
        """Test that history initializes empty."""
        assert len(history.history) == 0
    
    def test_add_track(self, history):
        """Test adding a play event."""
        event = history.add_track("Song", "Artist", "Album")
        
        assert len(history.history) == 1
        assert event["type"] == "play"
        assert event["track"] == "Song"
        assert event["artist"] == "Artist"
        assert event["album"] == "Album"
    
    def test_add_skip(self, history):
        """Test adding a skip event."""
        event = history.add_skip("Song", "Artist")
        
        assert len(history.history) == 1
        assert event["type"] == "skip"
        assert event["track"] == "Song"
        assert event["artist"] == "Artist"
    
    def test_save_and_load(self, temp_history_file):
        """Test saving and loading history."""
        # Create and save
        history1 = ListeningHistory(temp_history_file)
        history1.add_track("Song A", "Artist A", "Album A")
        history1.add_skip("Song B", "Artist B")
        history1.save_to_file()
        
        # Load in new instance
        history2 = ListeningHistory(temp_history_file)
        
        assert len(history2.history) == 2
        assert history2.history[0]["track"] == "Song A"
        assert history2.history[1]["type"] == "skip"
    
    def test_get_recent_plays(self, history):
        """Test retrieving recent play events."""
        history.add_track("Song 1", "Artist 1", "Album 1")
        history.add_skip("Song 2", "Artist 2")
        history.add_track("Song 3", "Artist 3", "Album 3")
        
        recent = history.get_recent(limit=2)
        
        # Should return only plays, most recent first
        assert len(recent) == 2
        assert recent[0]["track"] == "Song 3"
        assert recent[1]["track"] == "Song 1"
    
    def test_get_recent_skips(self, history):
        """Test retrieving skip events."""
        history.add_track("Song 1", "Artist 1", "Album 1")
        history.add_skip("Song 2", "Artist 2")
        history.add_skip("Song 3", "Artist 3")
        
        skips = history.get_recent_skips(limit=2)
        
        assert len(skips) == 2
        assert all(s["type"] == "skip" for s in skips)
    
    def test_get_play_count(self, history):
        """Test counting total plays."""
        history.add_track("Song 1", "Artist 1", "Album 1")
        history.add_skip("Song 2", "Artist 2")
        history.add_track("Song 3", "Artist 3", "Album 3")
        
        count = history.get_play_count()
        assert count == 2
    
    def test_get_skip_count(self, history):
        """Test counting total skips."""
        history.add_track("Song 1", "Artist 1", "Album 1")
        history.add_skip("Song 2", "Artist 2")
        history.add_skip("Song 3", "Artist 3")
        
        count = history.get_skip_count()
        assert count == 2
    
    def test_get_play_frequency(self, history):
        """Test artist play frequency."""
        history.add_track("Song 1", "The Weeknd", "Album 1")
        history.add_track("Song 2", "The Weeknd", "Album 1")
        history.add_track("Song 3", "Drake", "Album 2")
        
        freq = history.get_play_frequency()
        
        assert freq["The Weeknd"] == 2
        assert freq["Drake"] == 1
    
    def test_get_play_frequency_by_artist(self, history):
        """Test filtering frequency by artist."""
        history.add_track("Song 1", "Artist A", "Album 1")
        history.add_track("Song 2", "Artist A", "Album 1")
        history.add_track("Song 3", "Artist B", "Album 2")
        
        freq = history.get_play_frequency(artist="Artist A")
        
        assert "Artist A" in freq
        assert freq["Artist A"] == 2
    
    def test_get_summary(self, history):
        """Test getting session summary."""
        history.add_track("Song 1", "Artist 1", "Album 1")
        history.add_track("Song 2", "Artist 1", "Album 1")
        history.add_track("Song 3", "Artist 2", "Album 2")
        history.add_skip("Skip Song", "Skip Artist")
        
        summary = history.get_summary()
        
        assert summary["total_plays"] == 3
        assert summary["total_skips"] == 1
        assert summary["unique_artists"] == 2
        assert summary["most_played_artist"] == "Artist 1"
        assert summary["most_played_count"] == 2
    
    def test_clear_history(self, history):
        """Test clearing history."""
        history.add_track("Song", "Artist", "Album")
        assert len(history.history) == 1
        
        history.clear()
        assert len(history.history) == 0
    
    def test_auto_save_on_tenth_play(self, temp_history_file):
        """Test that history auto-saves every 10 plays."""
        history = ListeningHistory(temp_history_file)
        
        # Add 9 plays (no save yet)
        for i in range(9):
            history.add_track(f"Song {i}", f"Artist {i}", "Album")
        
        # File should not have been created yet by auto-save
        # (It would exist from manual save only)
        
        # Add 10th play
        history.add_track("Song 10", "Artist 10", "Album")
        # Auto-save should have triggered
        
        # Verify we can reload
        history2 = ListeningHistory(temp_history_file)
        assert len(history2.history) >= 10


class TestListeningHistoryEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def history(self):
        """Create a history instance."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            self.temp_path = f.name
        yield ListeningHistory(self.temp_path)
        Path(self.temp_path).unlink(missing_ok=True)
    
    def test_empty_summary(self, history):
        """Test summary of empty history."""
        summary = history.get_summary()
        
        assert summary["total_plays"] == 0
        assert summary["total_skips"] == 0
        assert summary["unique_artists"] == 0
    
    def test_duplicate_artist_plays(self, history):
        """Test frequency with same artist multiple times."""
        for i in range(100):
            history.add_track(f"Song {i}", "Same Artist", "Album")
        
        freq = history.get_play_frequency()
        assert freq["Same Artist"] == 100
    
    def test_special_characters_in_metadata(self, history):
        """Test handling special characters in song metadata."""
        history.add_track("(It's Not) Goodbye", "SEVENTEEN", "Album: 邻·近")
        recent = history.get_recent(limit=1)
        
        assert len(recent) == 1
        assert recent[0]["track"] == "(It's Not) Goodbye"
    
    def test_unicode_handling(self, history):
        """Test handling unicode characters."""
        history.add_track("歌曲", "アーティスト", "アルバム")
        history.add_track("Música", "Artista", "Álbum")
        
        summary = history.get_summary()
        assert summary["unique_artists"] == 2
    
    def test_limit_boundary(self, history):
        """Test limit parameter boundaries."""
        for i in range(20):
            history.add_track(f"Song {i}", f"Artist {i}", "Album")
        
        # Test limit = 0
        recent = history.get_recent(limit=0)
        assert len(recent) == 0
        
        # Test limit larger than history
        recent = history.get_recent(limit=100)
        assert len(recent) == 20
    
    def test_timestamp_preservation(self, history):
        """Test that timestamps are preserved."""
        now = datetime.now()
        history.add_track("Song", "Artist", "Album", timestamp=now)
        
        recent = history.get_recent(limit=1)
        stored_time = datetime.fromisoformat(recent[0]["timestamp"])
        
        # Should be within 1 second
        assert abs((stored_time - now).total_seconds()) < 1
    
    def test_duration_field(self, history):
        """Test duration tracking."""
        history.add_track("Song", "Artist", "Album", duration=180)
        
        recent = history.get_recent(limit=1)
        assert recent[0]["duration"] == 180
    
    def test_load_malformed_json(self):
        """Test handling of malformed JSON file."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("{invalid json")
            temp_path = f.name
        
        try:
            history = ListeningHistory(temp_path)
            # Should initialize with empty history on error
            assert len(history.history) == 0
        finally:
            Path(temp_path).unlink(missing_ok=True)
