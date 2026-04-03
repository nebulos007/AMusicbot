"""
Music recommendation engine using GPT-4o for discovery recommendations.

Analyzes listening history to extract preferences (genres, artists) and
uses GPT to generate recommendations for NEW artists/songs the user
might enjoy based on their taste. Combines content analysis with AI-driven
discovery to suggest unexplored music.
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict, Counter
import logging
import math

# Conditional import for GPTMusicAssistant (to avoid circular imports)
TYPE_CHECKING = False
if TYPE_CHECKING:
    from utils.gpt_integration import GPTMusicAssistant

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
    
    def __init__(self, gpt_assistant: Optional["GPTMusicAssistant"] = None):
        """
        Initialize the recommendation engine.
        
        Args:
            gpt_assistant (GPTMusicAssistant, optional): GPT assistant for AI-driven
                                                         discovery recommendations.
                                                         If None, falls back to content-based filtering.
        """
        self.library: List[Dict] = []  # Full song library
        self.listening_history: List[Dict] = []  # User's past plays
        self.skip_history: Set[str] = set()  # Songs user skipped
        self.gpt_assistant = gpt_assistant  # GPT integration for new discoveries
        
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
        # Simple but expanded genre inference - in production would use metadata API
        artist_lower = artist.lower()
        
        # Pop artists
        if any(word in artist_lower for word in ["taylor", "ariana", "billie", "dua", "the weeknd"]):
            self.genre_preferences["pop"] += 1
        # Hip-hop/Rap
        elif any(word in artist_lower for word in ["drake", "travis", "post", "kendrick", "nas", "eminem", "jay-z"]):
            self.genre_preferences["hip-hop"] += 1
        # Rock/Metal (expanded)
        elif any(word in artist_lower for word in ["coldplay", "the killers", "radiohead", "a.f.i", "afi", "nine inch nails", "nin", "nirvana", "tool", "korn", "deftones", "metallica", "slipknot"]):
            self.genre_preferences["rock"] += 1
            if any(word in artist_lower for word in ["a.f.i", "afi", "nine inch nails", "nin", "metallica", "korn", "slipknot"]):
                self.genre_preferences["metal"] += 0.5
        # Electronic/EDM
        elif any(word in artist_lower for word in ["daft", "deadmau5", "skrillex", "tiësto", "avicii", "zedd"]):
            self.genre_preferences["electronic"] += 1
        # Jazz/Soul
        elif any(word in artist_lower for word in ["miles", "coltrane", "billie", "sinatra", "amy"]):
            self.genre_preferences["jazz"] += 1
        # Classical
        elif any(word in artist_lower for word in ["mozart", "beethoven", "bach", "chopin"]):
            self.genre_preferences["classical"] += 1
        else:
            # Default to indie for unknown artists
            self.genre_preferences["indie"] += 0.5
    
    def calculate_similarity(
        self,
        song1: Dict[str, str],
        song2: Dict[str, str]
    ) -> float:
        """
        Calculate similarity between two songs (0-1 scale).
        
        Based on shared genre and artist characteristics.
        - Same artist: +0.1 (penalized to encourage variety)
        - Related genre: +0.4
        - Artist in same genre: +0.3
        
        Args:
            song1 (dict): First song with 'track', 'artist' keys.
            song2 (dict): Second song with 'track', 'artist' keys.
        
        Returns:
            float: Similarity score from 0.0 to 1.0.
        """
        similarity = 0.0
        
        # Same artist (penalized to encourage diversity)
        # Only adds small bonus instead of large bonus
        if song1.get("artist") == song2.get("artist"):
            similarity += 0.1  # Reduced from 0.4 to avoid same-artist recommendations
        
        # Genre similarity (primary driver)
        artist1 = song1.get("artist", "").lower()
        artist2 = song2.get("artist", "").lower()
        
        # Check genre relationship
        if self._are_related_artists(artist1, artist2):
            similarity += 0.4
        
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
        """Infer genres for an artist (expanded detection)."""
        genres = []
        
        if any(word in artist for word in ["taylor", "ariana", "billie", "dua", "the weeknd"]):
            genres = ["pop"]
        elif any(word in artist for word in ["drake", "travis", "post", "kendrick", "nas", "eminem", "jay-z"]):
            genres = ["hip-hop"]
        elif any(word in artist for word in ["coldplay", "the killers", "radiohead", "a.f.i", "afi", "nine inch nails", "nin", "nirvana", "tool", "korn"]):
            genres = ["rock", "alternative"]
        elif any(word in artist for word in ["metallica", "slipknot", "deftones"]):
            genres = ["metal", "rock"]
        elif any(word in artist for word in ["daft", "deadmau5", "skrillex"]):
            genres = ["electronic"]
        elif any(word in artist for word in ["mozart", "beethoven", "bach"]):
            genres = ["classical"]
        else:
            genres = ["indie", "alternative"]
        
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
        Generate personalized recommendations using GPT for discovery.
        
        If GPT is available, generates NEW artist recommendations based on
        the user's library and listening history. Otherwise, falls back to
        content-based filtering from the library.
        
        GPT-based approach (preferred):
        - Analyzes user's top artists and genres
        - Suggests NEW artists to explore (not in current library)
        - Explains connections to user's demonstrated taste
        - Adapts to user's mood if specified
        
        Fallback approach (content-based):
        - Filters existing library by mood or similarity
        - Useful for offline operation or when GPT unavailable
        
        Args:
            context (dict, optional): User context including:
                - 'current_mood': User's mood preference
                - 'user_message': The user's request (for context)
                - 'conversation_history': Previous conversation turns
            count (int): Number of recommendations (default 10).
        
        Returns:
            list of recommendation dicts. Format depends on recommender:
            - GPT-based: {'artist', 'reason', 'songs', 'raw_response'}
            - Content-based: {'track', 'artist', 'album', 'reason', 'score'}
        """
        if not self.library:
            logger.warning("No library loaded, cannot generate recommendations")
            return []
        
        context = context or {}
        
        # Try GPT-based discovery first (if available)
        if self.gpt_assistant:
            logger.debug("Using GPT-based discovery recommendations")
            return self.generate_discovery_recommendations(context, count)
        
        # Fallback to content-based filtering
        logger.debug("GPT not available, falling back to content-based recommendations")
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
    
    def get_library_summary(self) -> Dict:
        """
        Extract a summary of the user's library for GPT context.
        
        This provides GPT with key information about what's in the user's
        collection, their listening patterns, and preferences. Used to
        generate NEW artist recommendations that fit their taste.
        
        Returns:
            dict with:
                - 'top_artists': List of 5 most-played artists
                - 'top_genres': List of 3 most-preferred genres
                - 'total_songs': Total songs in library
                - 'unique_artists': Number of unique artists
                - 'play_count': Number of tracks played in session
                - 'library_sample': Dict with artist→album→track structure
                                   (top 50 artists, 2 albums each)
        """
        # Group library by artist for structure
        library_by_artist = defaultdict(lambda: defaultdict(list))
        for song in self.library:
            artist = song.get("artist", "Unknown")
            album = song.get("album", "Unknown")
            track = song.get("track", "Unknown")
            library_by_artist[artist][album].append(track)
        
        # Sample: top 50 artists, max 2 albums per artist, max 2 tracks per album
        library_sample = {}
        for artist in self.top_artists[:50]:
            albums_dict = {}
            for album in list(library_by_artist[artist].keys())[:2]:
                tracks = library_by_artist[artist][album][:2]
                albums_dict[album] = tracks
            if albums_dict:
                library_sample[artist] = albums_dict
        
        return {
            "top_artists": self.top_artists[:5],
            "top_genres": self.top_genres[:3],
            "total_songs": len(self.library),
            "unique_artists": len(self.artist_preferences),
            "play_count": len(self.listening_history),
            "library_sample": library_sample
        }
    
    def generate_discovery_recommendations(
        self,
        context: Optional[Dict] = None,
        count: int = 5
    ) -> List[Dict]:
        """
        Generate discovery recommendations using GPT-4o.
        
        Sends the user's library summary and listening context to GPT,
        which generates NEW artists/songs the user might explore based
        on their demonstrated taste.
        
        This is the core of the new recommendation strategy:
        - Input: What user already owns + listening patterns
        - Output: NEW artists to discover (not in current library)
        
        Args:
            context (dict, optional): User context including 'current_mood', 'chat_history', etc.
            count (int): Number of artist recommendations to request.
        
        Returns:
            list of recommendation dicts with 'artist', 'reason', 'songs' keys.
            If GPT unavailable, falls back to empty list.
        """
        if not self.gpt_assistant:
            logger.warning("GPT assistant not available, cannot generate discovery recommendations")
            return []
        
        if not self.library:
            logger.warning("No library loaded, cannot generate recommendations")
            return []
        
        context = context or {}
        
        # Build context for GPT
        library_summary = self.get_library_summary()
        mood = context.get("current_mood", "no specific mood")
        user_message = context.get("user_message", "")
        
        # Build the discovery prompt
        discovery_prompt = f"""Based on the following user's music library and listening history, 
suggest {count} NEW artists they should explore. These should be artists NOT already in their collection,
but similar to or complementary with their taste.

User's Current Taste:
- Favorite artists: {', '.join(library_summary['top_artists'])}
- Favorite genres: {', '.join(library_summary['top_genres'])}
- Total songs in library: {library_summary['total_songs']} across {library_summary['unique_artists']} artists
- Current mood: {mood}

Library Sample (what they own):
{self._format_library_sample_for_llm(library_summary['library_sample'])}

User request context: {user_message if user_message else "General recommendation"}

Please suggest {count} NEW artists they should discover. For each artist, provide:
1. Artist name
2. Why they'd like them (connection to their taste)
3. 2-3 song recommendations to start with

IMPORTANT: Use this EXACT format (with pipe separators):
Artist Name | Why they'd like them | Suggested songs: Song1, Song2, Song3

Example:
Leon Bridges | Soulful R&B with retro vibes, similar to Aloe Blacc | Suggested songs: River, Bad Bad News, Smooth Sailin'
Portugal. The Man | Indie rock with funk energy for upbeat moods | Suggested songs: Feel It Still, Evil Friends
"""
        
        try:
            # Call GPT with listening context
            listening_context = {
                "current_mood": mood,
                "top_genres": library_summary["top_genres"],
                "top_artists": library_summary["top_artists"],
                "play_count": library_summary["play_count"]
            }
            
            gpt_response = self.gpt_assistant.chat(
                user_message=discovery_prompt,
                listening_context=listening_context,
                conversation_history=context.get("conversation_history")
            )
            
            # Parse GPT response into recommendations
            recommendations = self._parse_gpt_discovery_response(gpt_response)
            
            logger.info(f"Generated {len(recommendations)} discovery recommendations via GPT")
            return recommendations
        
        except Exception as e:
            logger.error(f"Failed to generate discovery recommendations: {e}")
            return []
    
    def _format_library_sample_for_llm(self, library_sample: Dict) -> str:
        """
        Format library sample as readable text for GPT input.
        
        Args:
            library_sample (dict): Library sample from get_library_summary()
        
        Returns:
            str: Formatted text representation.
        """
        lines = []
        for artist, albums in library_sample.items():
            for album, tracks in albums.items():
                track_list = ", ".join(tracks)
                lines.append(f"  - {artist}: {album} ({track_list})")
        return "\n".join(lines) if lines else "  (Library sample unavailable)"
    
    def _parse_gpt_discovery_response(self, response: str) -> List[Dict]:
        """
        Parse GPT's discovery recommendation response.
        
        Converts GPT's text response into structured recommendation objects
        with Apple Music search URLs for easy discovery.
        
        Expected format:
            Artist Name | Reason | Suggested songs: Song1, Song2, Song3
        
        Args:
            response (str): Raw GPT response text.
        
        Returns:
            list of dicts with 'artist', 'reason', 'songs', 'apple_music_url', 'raw_response' keys.
        """
        # Late import to avoid circular dependency
        try:
            from apple_music import AppleMusicController
            controller = AppleMusicController()
        except Exception:
            controller = None
        
        recommendations = []
        
        # Split response into individual recommendations (separated by newlines)
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('-') or line.startswith('#'):
                continue
            
            # Try to parse pipe-separated format
            try:
                parts = line.split('|')
                if len(parts) >= 2:
                    artist = parts[0].strip()
                    reason = parts[1].strip()
                    
                    # Clean up markdown, numbering, and headers from GPT response
                    # Remove patterns like "1. **Artist Name**", "### 1. Artist", etc.
                    artist = artist.lstrip('0123456789.# ')  # Remove leading numbers, bullets, headers
                    artist = artist.replace('**', '').replace('*', '').replace('###', '').replace('##', '').replace('#', '')
                    artist = artist.strip()
                    
                    # Skip if artist is empty after cleaning
                    if not artist:
                        continue
                    
                    songs = []
                    if len(parts) >= 3:
                        # Extract songs from "Suggested songs: Song1, Song2, ..."
                        songs_part = parts[2].strip()
                        if ":" in songs_part:
                            songs_part = songs_part.split(":", 1)[1].strip()
                        # Clean up markdown from song names too
                        songs = [s.strip().replace('**', '').replace('*', '').replace('- ', '') for s in songs_part.split(",")]
                    
                    # Generate Apple Music search URL
                    apple_music_url = ""
                    if controller and songs:
                        # Use first suggested song for the URL (cleaned)
                        apple_music_url = controller.get_apple_music_search_url(songs[0], artist)
                    elif controller:
                        # No specific song, just search for artist
                        apple_music_url = controller.get_apple_music_search_url(artist)
                    
                    recommendations.append({
                        "artist": artist,
                        "reason": reason,
                        "songs": songs,
                        "apple_music_url": apple_music_url,
                        "raw_response": line
                    })
            except Exception as e:
                logger.debug(f"Could not parse GPT recommendation line '{line}': {e}")
                continue
        
        # If no recommendations parsed, return raw response wrapped
        if not recommendations:
            logger.warning(f"No structured recommendations. Response:\n{response[:200]}")
            return [{
                "artist": "Discovery Recommendations",
                "reason": response,
                "songs": [],
                "apple_music_url": "",
                "raw_response": response
            }]
        
        logger.info(f"Parsed {len(recommendations)} recommendations")
        return recommendations
