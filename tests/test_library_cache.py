"""
Unit tests for LibraryCache module.

Tests persistent JSON-based caching of music library metadata.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from library_cache import LibraryCache


class TestLibraryCache:
    """Test suite for LibraryCache class."""

    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_path = f.name
        yield cache_path
        # Cleanup
        Path(cache_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_library(self):
        """Sample music library for testing."""
        return [
            {
                "title": "Blinding Lights",
                "artist": "The Weeknd",
                "album": "After Hours",
                "duration": 200,
                "genre": "Synthwave"
            },
            {
                "title": "Running Up That Hill",
                "artist": "Kate Bush",
                "album": "Hounds of Love",
                "duration": 306,
                "genre": "Art Pop"
            },
            {
                "title": "Bohemian Rhapsody",
                "artist": "Queen",
                "album": "A Night at the Opera",
                "duration": 354,
                "genre": "Rock"
            }
        ]

    def test_init_creates_new_cache_object(self, temp_cache_file):
        """Test LibraryCache initialization."""
        cache = LibraryCache(temp_cache_file)
        assert cache.cache_file == Path(temp_cache_file)
        assert cache.library == []
        assert cache.is_loaded is False

    def test_load_from_cache_returns_false_when_no_file(self, temp_cache_file):
        """Test load_from_cache returns False when cache file doesn't exist."""
        cache = LibraryCache(temp_cache_file)
        result = cache.load_from_cache()
        assert result is False
        assert cache.is_loaded is False

    def test_save_to_cache_creates_file(self, temp_cache_file, sample_library):
        """Test save_to_cache creates JSON file with correct structure."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)

        assert Path(temp_cache_file).exists()
        
        # Verify file contents
        with open(temp_cache_file, 'r') as f:
            data = json.load(f)
        
        assert "songs" in data
        assert len(data["songs"]) == 3
        assert data["songs"][0]["title"] == "Blinding Lights"

    def test_load_from_cache_success(self, temp_cache_file, sample_library):
        """Test load_from_cache successfully loads cached library."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)

        # Create new cache object and load
        cache2 = LibraryCache(temp_cache_file)
        result = cache2.load_from_cache()

        assert result is True
        assert cache2.is_loaded is True
        assert len(cache2.library) == 3
        assert cache2.library[0]["title"] == "Blinding Lights"

    def test_get_library_returns_loaded_songs(self, temp_cache_file, sample_library):
        """Test get_library returns the cached library."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)
        cache.load_from_cache()

        library = cache.get_library()
        assert len(library) == 3
        assert library[0]["artist"] == "The Weeknd"

    def test_get_library_returns_empty_when_not_loaded(self, temp_cache_file):
        """Test get_library returns empty list when cache not loaded."""
        cache = LibraryCache(temp_cache_file)
        library = cache.get_library()
        assert library == []

    def test_clear_cache_removes_file(self, temp_cache_file, sample_library):
        """Test clear_cache removes the cache file."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)
        assert Path(temp_cache_file).exists()

        cache.clear_cache()
        assert not Path(temp_cache_file).exists()
        assert cache.is_loaded is False
        assert cache.library == []

    def test_get_cache_info_returns_metadata(self, temp_cache_file, sample_library):
        """Test get_cache_info returns correct metadata."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)

        info = cache.get_cache_info()
        assert info["exists"] is True
        assert info["path"] == str(Path(temp_cache_file).absolute())
        assert info["song_count"] == 3
        assert info["file_size_mb"] > 0
        assert "last_modified" in info

    def test_get_cache_info_when_no_cache(self, temp_cache_file):
        """Test get_cache_info when cache doesn't exist."""
        cache = LibraryCache(temp_cache_file)
        info = cache.get_cache_info()

        assert info["exists"] is False
        assert info["song_count"] == 0
        assert info["file_size_mb"] == 0

    def test_cache_preserves_all_song_metadata(self, temp_cache_file):
        """Test cache preserves all song metadata fields."""
        original_song = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180,
            "genre": "Test Genre",
            "year": 2024,
            "custom_field": "custom_value"
        }
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache([original_song])
        cache.load_from_cache()

        loaded_song = cache.library[0]
        assert loaded_song["title"] == original_song["title"]
        assert loaded_song["custom_field"] == original_song["custom_field"]
        assert loaded_song == original_song

    def test_cache_file_is_valid_json(self, temp_cache_file, sample_library):
        """Test cache produces valid JSON file."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)

        # Should not raise exception
        with open(temp_cache_file, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert isinstance(data.get("songs"), list)

    def test_cache_survives_multiple_save_load_cycles(self, temp_cache_file):
        """Test cache works across multiple save/load cycles."""
        library1 = [{"title": "Song 1", "artist": "Artist 1"}]
        library2 = [
            {"title": "Song 2", "artist": "Artist 2"},
            {"title": "Song 3", "artist": "Artist 3"}
        ]

        # First cycle
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(library1)
        cache.load_from_cache()
        assert len(cache.library) == 1

        # Second cycle (overwrite)
        cache.clear_cache()
        cache.save_to_cache(library2)
        cache.load_from_cache()
        assert len(cache.library) == 2

    def test_large_library_caching(self, temp_cache_file):
        """Test caching works with large libraries (performance test)."""
        # Create large library
        large_library = [
            {
                "title": f"Song {i}",
                "artist": f"Artist {i % 100}",
                "album": f"Album {i % 50}",
                "duration": 180 + (i % 120),
                "genre": ["Rock", "Pop", "Jazz", "Electronic"][i % 4]
            }
            for i in range(1000)
        ]

        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(large_library)

        cache2 = LibraryCache(temp_cache_file)
        result = cache2.load_from_cache()

        assert result is True
        assert len(cache2.library) == 1000

    def test_concurrent_save_operations(self, temp_cache_file):
        """Test that concurrent saves don't corrupt cache."""
        library = [{"title": "Song", "artist": "Artist"}]

        cache1 = LibraryCache(temp_cache_file)
        cache1.save_to_cache(library)

        cache2 = LibraryCache(temp_cache_file)
        cache2.save_to_cache(library)

        cache3 = LibraryCache(temp_cache_file)
        result = cache3.load_from_cache()

        # Should still be valid
        assert result is True
        assert len(cache3.library) == 1

    def test_cache_with_special_characters(self, temp_cache_file):
        """Test cache handles special characters in song metadata."""
        special_library = [
            {
                "title": "Café ☕",
                "artist": "Björk",
                "album": "Ágætis byrjun",
                "duration": 180,
                "genre": "Electronic 🎵"
            }
        ]

        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(special_library)
        cache.load_from_cache()

        song = cache.library[0]
        assert song["title"] == "Café ☕"
        assert song["artist"] == "Björk"
        assert "🎵" in song["genre"]

    def test_cache_handles_empty_library(self, temp_cache_file):
        """Test cache handles empty library correctly."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache([])

        cache2 = LibraryCache(temp_cache_file)
        result = cache2.load_from_cache()

        assert result is True
        assert len(cache2.library) == 0
        assert cache2.is_loaded is True

    def test_cache_info_after_load(self, temp_cache_file, sample_library):
        """Test get_cache_info provides accurate info after loading."""
        cache = LibraryCache(temp_cache_file)
        cache.save_to_cache(sample_library)
        cache.load_from_cache()

        info = cache.get_cache_info()
        assert info["exists"] is True
        assert info["song_count"] == 3
        assert "last_modified" in info

    def test_cache_path_handling(self):
        """Test cache handles various path formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test absolute path
            cache_path = Path(tmpdir) / "test_cache.json"
            cache = LibraryCache(str(cache_path))
            assert cache.cache_file == cache_path

            # Test Path object
            cache2 = LibraryCache(cache_path)
            assert cache2.cache_file == cache_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
