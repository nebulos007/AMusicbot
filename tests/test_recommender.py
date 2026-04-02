"""
Unit tests for the music recommendation engine.

Tests content-based filtering, similarity calculations, and preference analysis.
"""

import pytest
from recommender import MusicRecommender


class TestMusicRecommender:
    """Test suite for MusicRecommender class."""
    
    @pytest.fixture
    def recommender(self):
        """Create a recommender instance for testing."""
        return MusicRecommender()
    
    @pytest.fixture
    def sample_library(self):
        """Sample music library for testing."""
        return [
            {"track": "Blinding Lights", "artist": "The Weeknd", "album": "After Hours"},
            {"track": "Starboy", "artist": "The Weeknd", "album": "Starboy"},
            {"track": "Levitating", "artist": "Dua Lipa", "album": "Future Nostalgia"},
            {"track": "Good as Hell", "artist": "Lizzo", "album": "Cuz I Love You"},
            {"track": "Levitate", "artist": "Twenty One Pilots", "album": "Trench"},
            {"track": "Middle Child", "artist": "J. Cole", "album": "KOD"},
            {"track": "HUMBLE", "artist": "Kendrick Lamar", "album": "DAMN."},
            {"track": "Nights", "artist": "Frank Ocean", "album": "Blonde"},
            {"track": "Bohemian Rhapsody", "artist": "Queen", "album": "A Night at the Opera"},
            {"track": "Imagine", "artist": "John Lennon", "album": "Imagine"},
        ]
    
    @pytest.fixture
    def sample_history(self):
        """Sample listening history for testing."""
        return [
            {"track": "Blinding Lights", "artist": "The Weeknd", "album": "After Hours"},
            {"track": "Starboy", "artist": "The Weeknd", "album": "Starboy"},
            {"track": "Levitating", "artist": "Dua Lipa", "album": "Future Nostalgia"},
            {"track": "Good as Hell", "artist": "Lizzo", "album": "Cuz I Love You"},
            {"track": "Levitate", "artist": "Twenty One Pilots", "album": "Trench"},
        ]
    
    def test_initialization(self, recommender):
        """Test that recommender initializes with empty data."""
        assert recommender.library == []
        assert recommender.listening_history == []
        assert len(recommender.genre_preferences) == 0
    
    def test_load_library(self, recommender, sample_library):
        """Test loading library."""
        recommender.load_library(sample_library)
        assert len(recommender.library) == len(sample_library)
        assert recommender.library[0]["track"] == "Blinding Lights"
    
    def test_load_listening_history(self, recommender, sample_library, sample_history):
        """Test loading listening history and preference analysis."""
        recommender.load_library(sample_library)
        recommender.load_listening_history(sample_history)
        
        assert len(recommender.listening_history) == len(sample_history)
        assert "The Weeknd" in recommender.artist_preferences
        assert recommender.artist_preferences["The Weeknd"] == 2  # 2 plays
    
    def test_add_play_event(self, recommender):
        """Test adding a play event."""
        recommender.add_play_event("Blinding Lights", "The Weeknd", "After Hours")
        
        assert len(recommender.listening_history) == 1
        assert recommender.artist_preferences["The Weeknd"] == 1
    
    def test_add_skip_event(self, recommender):
        """Test adding a skip event."""
        recommender.add_skip_event("Bad Song", "Unknown Artist")
        
        assert "Bad Song|Unknown Artist" in recommender.skip_history
        assert len(recommender.skip_history) == 1
    
    def test_calculate_similarity_same_artist(self, recommender):
        """Test similarity calculation for same artist."""
        song1 = {"track": "Song A", "artist": "Artist X"}
        song2 = {"track": "Song B", "artist": "Artist X"}
        
        similarity = recommender.calculate_similarity(song1, song2)
        assert similarity >= 0.3  # Should be high for same artist
    
    def test_calculate_similarity_different_artist(self, recommender):
        """Test similarity calculation for different artists."""
        song1 = {"track": "Song A", "artist": "Artist X"}
        song2 = {"track": "Song B", "artist": "Artist Y"}
        
        similarity = recommender.calculate_similarity(song1, song2)
        # Similarity should be lower, but not zero due to genre inference
        assert 0 <= similarity <= 1
    
    def test_calculate_similarity_penalize_skips(self, recommender):
        """Test that skipped songs are penalized."""
        recommender.add_skip_event("Bad Song", "Bad Artist")
        
        song1 = {"track": "Another Song", "artist": "Good Artist"}
        song2 = {"track": "Bad Song", "artist": "Bad Artist"}
        
        similarity = recommender.calculate_similarity(song1, song2)
        assert similarity < 0.1  # Should be penalized
    
    def test_recommend_by_mood(self, recommender, sample_library):
        """Test mood-based recommendations."""
        recommender.load_library(sample_library)
        
        recommendations = recommender.recommend_by_mood("chill", count=5)
        
        assert len(recommendations) > 0
        assert len(recommendations) <= 5
        assert "track" in recommendations[0]
        assert "artist" in recommendations[0]
        assert "reason" in recommendations[0]
    
    def test_recommend_by_artist(self, recommender, sample_library):
        """Test artist-based recommendations."""
        recommender.load_library(sample_library)
        
        recommendations = recommender.recommend_by_artist("The Weeknd", count=5)
        
        assert len(recommendations) > 0
        assert all("track" in rec for rec in recommendations)
    
    def test_recommendations_exclude_skips(self, recommender, sample_library):
        """Test that skipped songs are excluded from recommendations."""
        recommender.load_library(sample_library)
        recommender.add_skip_event("Blinding Lights", "The Weeknd")
        
        recommendations = recommender.recommend_by_artist("The Weeknd", count=10)
        
        # Skipped song should not appear
        skipped_tracks = [r for r in recommendations if r["track"] == "Blinding Lights"]
        assert len(skipped_tracks) == 0
    
    def test_get_preference_summary(self, recommender, sample_library, sample_history):
        """Test preference summary."""
        recommender.load_library(sample_library)
        recommender.load_listening_history(sample_history)
        
        summary = recommender.get_preference_summary()
        
        assert "top_genres" in summary
        assert "top_artists" in summary
        assert summary["play_count"] == len(sample_history)
    
    def test_get_recommendations_with_empty_library(self, recommender):
        """Test recommendations with empty library."""
        recommendations = recommender.get_recommendations(count=10)
        
        assert recommendations == []
    
    def test_get_recommendations_with_mood_context(self, recommender, sample_library):
        """Test recommendations with mood context."""
        recommender.load_library(sample_library)
        
        context = {"current_mood": "energetic"}
        recommendations = recommender.get_recommendations(context, count=5)
        
        assert len(recommendations) <= 5
        assert all("track" in rec for rec in recommendations)


class TestRecommendationEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def recommender(self):
        """Create a recommender instance."""
        return MusicRecommender()
    
    def test_empty_listening_history(self, recommender):
        """Test behavior with no listening history."""
        recommender.load_library([
            {"track": "Song A", "artist": "Artist A", "album": "Album A"}
        ])
        
        recommendations = recommender.get_recommendations(count=5)
        # Should still return recommendations based on library
        assert isinstance(recommendations, list)
    
    def test_similarity_bounds(self, recommender):
        """Test that similarity is always between 0 and 1."""
        song1 = {"track": "A", "artist": "X"}
        song2 = {"track": "B", "artist": "Y"}
        
        for _ in range(10):
            sim = recommender.calculate_similarity(song1, song2)
            assert 0 <= sim <= 1
    
    def test_duplicate_song_skips(self, recommender):
        """Test handling duplicate skip events."""
        recommender.add_skip_event("Song", "Artist")
        recommender.add_skip_event("Song", "Artist")
        
        # Should only add unique skips
        assert len(recommender.skip_history) == 1
    
    def test_large_library_handling(self, recommender):
        """Test handling large libraries."""
        large_library = [
            {"track": f"Song {i}", "artist": f"Artist {i % 100}", "album": f"Album {i % 50}"}
            for i in range(1000)
        ]
        
        recommender.load_library(large_library)
        recommendations = recommender.get_recommendations(count=10)
        
        assert len(recommendations) <= 10
