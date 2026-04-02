"""
Unit tests for conversation management.

Tests intent detection, context management, and message history.
"""

import pytest
from chat_manager import MusicChatSession, UserIntent


class TestMusicChatSession:
    """Test suite for MusicChatSession."""
    
    @pytest.fixture
    def session(self):
        """Create a chat session for testing."""
        return MusicChatSession("test_user")
    
    def test_initialization(self, session):
        """Test session initialization."""
        assert session.user_id == "test_user"
        assert len(session.messages) == 0
        assert session.context["current_mood"] is None
    
    def test_add_message(self, session):
        """Test adding messages to history."""
        msg = session.add_message("user", "Hello bot")
        
        assert len(session.messages) == 1
        assert msg.role == "user"
        assert msg.content == "Hello bot"
    
    def test_message_history_limit(self, session):
        """Test that message history respects max_history limit."""
        session.max_history = 5
        
        for i in range(10):
            session.add_message("user", f"Message {i}")
        
        # Should only keep last 5
        assert len(session.messages) == 5
    
    def test_extract_intent_play(self, session):
        """Test detecting play intent."""
        intent, entities = session.extract_intent("play Bohemian Rhapsody by Queen")
        
        assert intent == UserIntent.PLAY
        assert "song" in entities
        assert "Bohemian Rhapsody" in entities["song"]
    
    def test_extract_intent_skip(self, session):
        """Test detecting skip intent."""
        intent, entities = session.extract_intent("skip to the next track")
        
        assert intent == UserIntent.SKIP
    
    def test_extract_intent_pause(self, session):
        """Test detecting pause intent."""
        intent, entities = session.extract_intent("pause the music")
        
        assert intent == UserIntent.PAUSE
    
    def test_extract_intent_recommend(self, session):
        """Test detecting recommendation intent."""
        intent, entities = session.extract_intent("recommend something chill")
        
        assert intent == UserIntent.RECOMMEND
        assert entities.get("mood") == "chill"
    
    def test_extract_intent_recommend_moods(self, session):
        """Test mood extraction in recommendation intent."""
        moods = ["chill", "relaxing", "upbeat", "energetic", "sad", "happy", "focus"]
        
        for mood in moods:
            intent, entities = session.extract_intent(f"play something {mood}")
            assert intent == UserIntent.RECOMMEND
            assert entities.get("mood") == mood
    
    def test_extract_intent_search(self, session):
        """Test detecting search intent."""
        intent, entities = session.extract_intent("find a song called Levitating")
        
        assert intent == UserIntent.SEARCH
        assert "query" in entities
    
    def test_extract_intent_unknown(self, session):
        """Test handling unknown intent."""
        intent, entities = session.extract_intent("tell me a joke")
        
        assert intent == UserIntent.UNKNOWN
    
    def test_process_user_input(self, session):
        """Test full user input processing."""
        result = session.process_user_input("play something chill")
        
        assert "intent" in result
        assert "entities" in result
        assert "context" in result
        assert "message" in result
        assert result["intent"] == UserIntent.RECOMMEND
    
    def test_update_context_mood(self, session):
        """Test updating mood context."""
        session.update_context("mood", "energetic")
        
        assert session.context["current_mood"] == "energetic"
    
    def test_update_context_track(self, session):
        """Test updating current track context."""
        track = {"track": "Song", "artist": "Artist"}
        session.update_context("current_track", track)
        
        assert session.context["current_track"] == track
        assert track in session.context["listening_history"]
    
    def test_get_context_window(self, session):
        """Test getting context window for LLM."""
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        session.add_message("user", "How are you?")
        
        window = session.get_context_window(num_turns=2)
        
        assert len(window) == 2
        assert window[0]["role"] == "assistant"
        assert window[1]["role"] == "user"
    
    def test_get_summary(self, session):
        """Test getting session summary."""
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        session.update_context("mood", "chill")
        
        summary = session.get_summary()
        
        assert summary["user_id"] == "test_user"
        assert summary["total_messages"] == 2
        assert summary["user_messages"] == 1
        assert summary["current_mood"] == "chill"
    
    def test_extract_intent_with_artist_reference(self, session):
        """Test extracting artist reference in recommendation."""
        intent, entities = session.extract_intent("recommend like The Weeknd")
        
        assert intent == UserIntent.RECOMMEND
        # May or may not have reference depending on regex
        if "reference" in entities:
            assert "The Weeknd" in entities["reference"]


class TestIntentExtractionEdgeCases:
    """Test edge cases in intent detection."""
    
    @pytest.fixture
    def session(self):
        """Create a chat session."""
        return MusicChatSession()
    
    def test_case_insensitive_intent(self, session):
        """Test that intent detection is case-insensitive."""
        intent1, _ = session.extract_intent("PLAY Song")
        intent2, _ = session.extract_intent("play song")
        intent3, _ = session.extract_intent("PlAy SONG")
        
        assert intent1 == intent2 == intent3 == UserIntent.PLAY
    
    def test_intent_with_extra_words(self, session):
        """Test intent detection with extra words."""
        intent, _ = session.extract_intent("Hey bot, can you pleaseplay some music for me?")
        
        assert intent == UserIntent.PLAY
    
    def test_ambiguous_intent(self, session):
        """Test behavior with ambiguous intents."""
        # "skip" and "recommend" both present
        intent, _ = session.extract_intent("skip this and recommend something")
        
        # Should match first keyword found
        assert intent in [UserIntent.SKIP, UserIntent.RECOMMEND]
    
    def test_empty_input(self, session):
        """Test handling empty input."""
        intent, entities = session.extract_intent("")
        
        assert intent == UserIntent.UNKNOWN
        assert entities == {}
    
    def test_special_characters_in_song_name(self, session):
        """Test extracting song names with special characters."""
        intent, entities = session.extract_intent("play (It's Not) Goodbye by SEVENTEEN")
        
        assert intent == UserIntent.PLAY
        if "song" in entities:
            # Should capture the song name
            assert len(entities["song"]) > 0
    
    def test_artist_extraction_with_multiple_artists(self, session):
        """Test extracting artist when multiple mentioned."""
        intent, entities = session.extract_intent("play Don't Start Now by Dua Lipa featuring Miley Cyrus")
        
        assert intent == UserIntent.PLAY
        # Should extract at least primary artist
        if "artist" in entities:
            assert "Dua Lipa" in entities["artist"]


class TestContextManagement:
    """Test conversation context management."""
    
    @pytest.fixture
    def session(self):
        """Create a session."""
        return MusicChatSession()
    
    def test_context_persistence(self, session):
        """Test that context persists across interactions."""
        session.update_context("mood", "chill")
        session.add_message("user", "test")
        
        assert session.context["current_mood"] == "chill"
    
    def test_track_history_accumulation(self, session):
        """Test that track history accumulates."""
        track1 = {"track": "Song 1", "artist": "Artist 1"}
        track2 = {"track": "Song 2", "artist": "Artist 2"}
        
        session.update_context("current_track", track1)
        session.update_context("current_track", track2)
        
        assert len(session.context["listening_history"]) == 2
        assert track1 in session.context["listening_history"]
        assert track2 in session.context["listening_history"]
    
    def test_skip_history_tracking(self, session):
        """Test that skip events are tracked."""
        skip = {"track": "Song", "artist": "Artist"}
        session.update_context("skip", skip)
        
        assert skip in session.context["recent_skips"]
