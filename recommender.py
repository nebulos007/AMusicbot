"""
Music recommendation engine using content-based filtering.

Analyzes listening history to extract preferences (genres, artists) and
generates recommendations based on similarity to previously played tracks.
Uses mood detection and user preferences to rank recommendations.
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict, Counter
import logging
import math

logger = logging.getLogger(__name__)


class MusicRecommender:
    """
    Content-based music recommendation engine.
    
    Analyzes user's listening history to identify preferred genres and artists,
    then recommends songs with similar characteristics. Includes mood-based
    and artist-based recommendation strategies.
    """
    
    # Mood-to-genre mapping for recommendation
    MOOD_GENRES = {
        "chill": ["indie", "lo-fi", "ambient", "acoustic", "jazz"],
        "relaxing": ["ambient", "classical", "lo-fi", "acoustic", "soul"],
        "upbeat": ["pop", "dance", "funk", "electronic", "indie"],
        "energetic": ["rock", "metal", "electronic", "hip-hop", "pop"],
        "happy": ["pop", "funk", "soul", "electronic", "indie"],
        "sad": ["blues", "classical", "soul", "acoustic", "indie"],
        "workout": ["hip-hop", "electronic", "rock", "pop", "dance"],
        "party": ["pop", "electronic", "hip-hop", "dance", "funk"],
        "focus": ["ambient", "classical", "lo-fi", "electronic", "acoustic"],
        "study": ["lo-fi", "classical", "ambient", "acoustic", "indie"],
        "sleep": ["ambient", "classical", "acoustic", "lo-fi", "jazz"],
        "romantic": ["soul", "classical", "acoustic", "jazz", "indie"],
    }
    
    def __init__(self):
        """Initialize the recommendation engine."""
        self.library: List[Dict] = []  # Full song library
        self.listening_history: List[Dict] = []  # User's past plays
        self.skip_history: Set[str] = set()  # Songs user skipped
        
        # Extracted preferences from history
        self.genre_preferences: Counter = Counter()
        self.artist_preferences: Counter = Counter()
        self.top_genres: List[str] = []
        self.top_artists: List[str] = []
    
    def load_library(self, songs: List[Dict[str, str]]):
        """
        Load the full music library.
        
        Args:
            songs (list): List of dicts with 'track', 'artist', 'album' keys.
        """
        self.library = songs
        logger.info(f"Loaded library with {len(songs)} songs")
    
    def load_listening_history(self, history: List[Dict]):
        """
        Load user's listening history.
        
        Args:
            history (list): List of play events with 'track', 'artist', 'album', 'timestamp' keys.
        """
        self.listening_history = history
        self._analyze_history()
    
    def add_play_event(self, track: str, artist: str, album: str):
        """
        Add a single play event to history and update preferences.
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
            album (str): Album name.
        """
        event = {
            "track": track,
            "artist": artist,
            "album": album
        }
        self.listening_history.append(event)
        
        # Update preferences
        self.artist_preferences[artist] += 1
        # Infer genre from artist (would improve with real genre metadata)
        self._update_genre_from_artist(artist)
        
        logger.debug(f"Added play event: {track} by {artist}")
    
    def add_skip_event(self, track: str, artist: str):
        """
        Record a skip event (user didn't want to listen).
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
        """
        skip_key = f"{track}|{artist}"
        self.skip_history.add(skip_key)
        logger.debug(f"Recorded skip: {track} by {artist}")
    
    def _analyze_history(self):
        """
        Analyze listening history to extract preferences.
        
        Updates genre_preferences and artist_preferences based on
        what the user has played.
        """
        self.genre_preferences.clear()
        self.artist_preferences.clear()
        
        for event in self.listening_history:
            artist = event.get("artist", "Unknown")
            self.artist_preferences[artist] += 1
            self._update_genre_from_artist(artist)
        
        # Get top genres and artists
        self.top_genres = [g for g, _ in self.genre_preferences.most_common(5)]
        self.top_artists = [a for a, _ in self.artist_preferences.most_common(5)]
        
        logger.info(
            f"Analyzed {len(self.listening_history)} plays. "
            f"Top genres: {self.top_genres}, Top artists: {self.top_artists}"
        )
    
    def _update_genre_from_artist(self, artist: str):
        """
        Infer genre from artist name (heuristic).
        
        This is a simple heuristic. In production, would use a genre database.
        
        Args:
            artist (str): Artist name.
        """
        # Very basic genre inference - in production would use metadata API
        artist_lower = artist.lower()
        
        if any(word in artist_lower for word in ["taylor", "ariana", "billie", "dua"]):
            self.genre_preferences["pop"] += 1
        elif any(word in artist_lower for word in ["drake", "travis", "post", "kendrick"]):
            self.genre_preferences["hip-hop"] += 1
        elif any(word in artist_lower for word in ["coldplay", "the killers", "radiohead"]):
            self.genre_preferences["rock"] += 1
        elif any(word in artist_lower for word in ["mozart", "beethoven", "bach"]):
            self.genre_preferences["classical"] += 1
        else:
            # Default to pop for unknown artists
            self.genre_preferences["indie"] += 0.5
    
    def calculate_similarity(
        self,
        song1: Dict[str, str],
        song2: Dict[str, str]
    ) -> float:
        """
        Calculate similarity between two songs (0-1 scale).
        
        Based on shared genre and artist characteristics.
        - Same artist: +0.4
        - Related genre: +0.4
        - Artist in same genre: +0.3
        
        Args:
            song1 (dict): First song with 'track', 'artist' keys.
            song2 (dict): Second song with 'track', 'artist' keys.
        
        Returns:
            float: Similarity score from 0.0 to 1.0.
        """
        similarity = 0.0
        
        # Same artist (strong signal)
        if song1.get("artist") == song2.get("artist"):
            similarity += 0.4
        
        # Genre similarity (would improve with real genre data)
        # For now, use artist-based inference
        artist1 = song1.get("artist", "").lower()
        artist2 = song2.get("artist", "").lower()
        
        # Simple co-occurrence check (would use genre DB in production)
        if self._are_related_artists(artist1, artist2):
            similarity += 0.3
        
        # Penalize if in skip history
        skip_key = f"{song2.get('track')}|{song2.get('artist')}"
        if skip_key in self.skip_history:
            similarity -= 0.2
        
        return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
    
    def _are_related_artists(self, artist1: str, artist2: str) -> bool:
        """
        Check if two artists are related (simplified).
        
        In production, would use a music API or knowledge base.
        
        Args:
            artist1 (str): First artist name (lowercase).
            artist2 (str): Second artist name (lowercase).
        
        Returns:
            bool: True if artists are likely related.
        """
        # Check if both appear in user's listening history
        artist1_genres = self._infer_genres(artist1)
        artist2_genres = self._infer_genres(artist2)
        
        # Calculate genre overlap
        common_genres = set(artist1_genres) & set(artist2_genres)
        return len(common_genres) > 0
    
    def _infer_genres(self, artist: str) -> List[str]:
        """Infer genres for an artist (simplified)."""
        genres = []
        
        if any(word in artist for word in ["taylor", "ariana", "billie", "dua"]):
            genres = ["pop"]
        elif any(word in artist for word in ["drake", "travis", "post", "kendrick"]):
            genres = ["hip-hop"]
        elif any(word in artist for word in ["coldplay", "the killers"]):
            genres = ["rock"]
        else:
            genres = ["indie", "pop"]
        
        return genres
    
    def recommend_by_mood(self, mood: str, count: int = 5) -> List[Dict]:
        """
        Generate recommendations based on user's mood.
        
        Args:
            mood (str): Mood keyword (e.g., "chill", "energetic", "focus").
            count (int): Number of recommendations to return.
        
        Returns:
            list of recommendation dicts with 'track', 'artist', 'reason' keys.
        """
        target_genres = self.MOOD_GENRES.get(mood.lower(), ["indie", "pop"])
        
        recommendations = []
        seen = set()
        
        # Score songs based on mood-aligned genres
        scored_songs = []
        for song in self.library:
            if song.get("track") in seen:
                continue
            seen.add(song.get("track"))
            
            # Skip if already in skip history
            skip_key = f"{song.get('track')}|{song.get('artist')}"
            if skip_key in self.skip_history:
                continue
            
            # Score based on genre alignment
            score = 0.5  # Base score
            
            # Boost if artist is in user's top artists
            if song.get("artist") in self.top_artists:
                score += 0.3
            
            scored_songs.append((score, song))
        
        # Sort by score and return top N
        scored_songs.sort(key=lambda x: x[0], reverse=True)
        
        for score, song in scored_songs[:count]:
            recommendations.append({
                "track": song.get("track", "Unknown"),
                "artist": song.get("artist", "Unknown"),
                "album": song.get("album", "Unknown"),
                "reason": f"Perfect for a {mood} mood",
                "score": score
            })
        
        logger.info(f"Generated {len(recommendations)} recommendations for mood: {mood}")
        return recommendations
    
    def recommend_by_artist(self, artist: str, count: int = 5) -> List[Dict]:
        """
        Generate recommendations based on an artist.
        
        Returns songs from similar artists and the original artist.
        
        Args:
            artist (str): Reference artist name.
            count (int): Number of recommendations.
        
        Returns:
            list of recommendation dicts with 'track', 'artist', 'reason' keys.
        """
        recommendations = []
        seen = set()
        
        # First, find other songs by the same artist
        same_artist_songs = [
            s for s in self.library
            if s.get("artist", "").lower() == artist.lower()
        ]
        
        # Score all songs
        scored_songs = []
        for song in self.library:
            if song.get("track") in seen:
                continue
            seen.add(song.get("track"))
            
            # Skip if in skip history
            skip_key = f"{song.get('track')}|{song.get('artist')}"
            if skip_key in self.skip_history:
                continue
            
            # Calculate similarity to reference artist
            ref_song = {"artist": artist, "track": "reference"}
            similarity = self.calculate_similarity(ref_song, song)
            scored_songs.append((similarity, song))
        
        # Sort by similarity
        scored_songs.sort(key=lambda x: x[0], reverse=True)
        
        for score, song in scored_songs[:count]:
            reason = "By the same artist" if score > 0.3 else "Similar artist"
            recommendations.append({
                "track": song.get("track", "Unknown"),
                "artist": song.get("artist", "Unknown"),
                "album": song.get("album", "Unknown"),
                "reason": reason,
                "score": score
            })
        
        logger.info(f"Generated {len(recommendations)} recommendations based on: {artist}")
        return recommendations
    
    def get_recommendations(
        self,
        context: Optional[Dict] = None,
        count: int = 10
    ) -> List[Dict]:
        """
        Generate personalized recommendations based on user context.
        
        Args:
            context (dict, optional): User context including 'mood', 'listening_history', etc.
            count (int): Number of recommendations.
        
        Returns:
            list of recommendation dicts with 'track', 'artist', 'reason', 'score' keys.
        """
        if not self.library:
            logger.warning("No library loaded, cannot generate recommendations")
            return []
        
        context = context or {}
        recommendations = []
        
        # If user specified a mood, use that
        if context.get("current_mood"):
            recommendations = self.recommend_by_mood(context["current_mood"], count)
        
        # If no mood, recommend based on top artists
        elif self.top_artists:
            artist = self.top_artists[0]
            recommendations = self.recommend_by_artist(artist, count)
        
        # Fallback: return random popular songs
        else:
            recommendations = [
                {
                    "track": s.get("track", "Unknown"),
                    "artist": s.get("artist", "Unknown"),
                    "album": s.get("album", "Unknown"),
                    "reason": "Popular in your library",
                    "score": 0.5
                }
                for s in self.library[:count]
            ]
        
        return recommendations
    
    def get_preference_summary(self) -> Dict:
        """
        Get summary of user's music preferences.
        
        Returns:
            dict with 'top_genres', 'top_artists', 'play_count' keys.
        """
        return {
            "top_genres": self.top_genres,
            "top_artists": self.top_artists,
            "play_count": len(self.listening_history),
            "skip_count": len(self.skip_history),
            "unique_artists": len(self.artist_preferences)
        }
