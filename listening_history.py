"""
Listening history persistence and management.

Loads initial listening history from Apple Music via AppleScript and maintains
a JSON file of all plays and skips during the session. This data is used to
build the user's preference profile over time.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ListeningHistory:
    """
    Manages user's listening history with persistent JSON storage.
    
    Initializes from Apple Music library on startup and automatically logs
    all play/skip events during the session. Data persists to disk to enable
    preference learning across sessions.
    """
    
    def __init__(self, history_file: str = "listening_history.json"):
        """
        Initialize listening history manager.
        
        Args:
            history_file (str): Path to JSON file for persistent storage.
                               Will be created if it doesn't exist.
        """
        self.history_file = Path(history_file)
        self.history: List[Dict] = []
        
        # Load existing history if available
        self._load_from_file()
    
    def _load_from_file(self) -> bool:
        """
        Load listening history from JSON file if it exists.
        
        Returns:
            bool: True if file was loaded, False if file doesn't exist yet.
        """
        if not self.history_file.exists():
            logger.info(f"No existing history file found at {self.history_file}")
            return False
        
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                self.history = data.get("plays", [])
                logger.info(f"Loaded {len(self.history)} history entries from {self.history_file}")
                return True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load history file: {e}")
            return False
    
    def save_to_file(self) -> bool:
        """
        Persist listening history to JSON file.
        
        Returns:
            bool: True if successfully saved.
        """
        try:
            data = {
                "plays": self.history,
                "last_updated": datetime.now().isoformat(),
                "total_plays": len(self.history)
            }
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug(f"Saved {len(self.history)} history entries to {self.history_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save history file: {e}")
            return False
    
    def add_track(
        self,
        track: str,
        artist: str,
        album: str,
        duration: int = 0,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Log a track play event.
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
            album (str): Album name.
            duration (int): Duration in seconds (optional).
            timestamp (datetime, optional): When the track was played.
                                          Defaults to now.
        
        Returns:
            dict: The play event that was added.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        event = {
            "type": "play",
            "track": track,
            "artist": artist,
            "album": album,
            "duration": duration,
            "timestamp": timestamp.isoformat()
        }
        
        self.history.append(event)
        logger.debug(f"Added play event: {track} by {artist}")
        
        # Auto-save periodically
        if len(self.history) % 10 == 0:
            self.save_to_file()
        
        return event
    
    def add_skip(
        self,
        track: str,
        artist: str,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Log a track skip event.
        
        Args:
            track (str): Track name that was skipped.
            artist (str): Artist name.
            timestamp (datetime, optional): When the skip occurred.
                                          Defaults to now.
        
        Returns:
            dict: The skip event that was added.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        event = {
            "type": "skip",
            "track": track,
            "artist": artist,
            "timestamp": timestamp.isoformat()
        }
        
        self.history.append(event)
        logger.debug(f"Added skip event: {track} by {artist}")
        
        return event
    
    def get_recent(self, limit: int = 50) -> List[Dict]:
        """
        Get most recent play events (excluding skips).
        
        Args:
            limit (int): Maximum number of events to return.
        
        Returns:
            list of play event dicts, most recent first.
        """
        plays = [e for e in self.history if e.get("type") == "play"]
        return plays[-limit:][::-1]  # Most recent first
    
    def get_recent_skips(self, limit: int = 20) -> List[Dict]:
        """
        Get most recent skip events.
        
        Args:
            limit (int): Maximum number of skips to return.
        
        Returns:
            list of skip event dicts, most recent first.
        """
        skips = [e for e in self.history if e.get("type") == "skip"]
        return skips[-limit:][::-1]  # Most recent first
    
    def get_play_count(self) -> int:
        """
        Get total number of plays in history.
        
        Returns:
            int: Total play count.
        """
        return sum(1 for e in self.history if e.get("type") == "play")
    
    def get_skip_count(self) -> int:
        """
        Get total number of skips in history.
        
        Returns:
            int: Total skip count.
        """
        return sum(1 for e in self.history if e.get("type") == "skip")
    
    def get_play_frequency(self, artist: Optional[str] = None) -> Dict[str, int]:
        """
        Get play frequency by artist or tracks.
        
        Args:
            artist (str, optional): If provided, get frequency for this artist only.
        
        Returns:
            dict: Maps artist/track to play count.
        """
        frequency = {}
        
        for event in self.history:
            if event.get("type") != "play":
                continue
            
            if artist and event.get("artist") != artist:
                continue
            
            key = event.get("artist", "Unknown")
            frequency[key] = frequency.get(key, 0) + 1
        
        # Sort by frequency
        return dict(sorted(frequency.items(), key=lambda x: x[1], reverse=True))
    
    def load_initial_from_applescript(self, apple_music_controller):
        """
        Load initial listening history from Apple Music via AppleScript.
        
        Attempts to query the currently playing or recently played tracks
        from Apple Music to bootstrap the session with some initial context.
        
        Args:
            apple_music_controller: AppleMusicController instance.
        
        Returns:
            bool: True if successfully loaded any tracks.
        """
        try:
            # Try to get current track
            current = apple_music_controller.get_current_track()
            if current:
                self.add_track(
                    current["track"],
                    current["artist"],
                    current.get("album", "Unknown"),
                    duration=int(current.get("duration", 0))
                )
                logger.info(f"Loaded current track from Apple Music: {current['track']}")
                return True
            
            logger.debug("No current track in Apple Music")
            return False
        
        except Exception as e:
            logger.warning(f"Failed to load initial history from Apple Music: {e}")
            return False
    
    def get_summary(self) -> Dict:
        """
        Get summary statistics of listening history.
        
        Returns:
            dict with keys: 'total_plays', 'total_skips', 'unique_artists',
                           'unique_tracks', 'most_played_artist', 'session_duration'
        """
        plays = self.get_recent(limit=float('inf'))
        skips = self.get_recent_skips(limit=float('inf'))
        
        # Extract unique artists and tracks
        artists = set(e.get("artist", "Unknown") for e in plays)
        tracks = set(e.get("track", "Unknown") for e in plays)
        
        # Find most played artist
        frequency = self.get_play_frequency()
        most_played = max(frequency.items(), key=lambda x: x[1]) if frequency else None
        
        return {
            "total_plays": len(plays),
            "total_skips": len(skips),
            "unique_artists": len(artists),
            "unique_tracks": len(tracks),
            "most_played_artist": most_played[0] if most_played else None,
            "most_played_count": most_played[1] if most_played else 0
        }
    
    def clear(self):
        """
        Clear all history.
        
        WARNING: This is destructive. Use with caution.
        """
        self.history = []
        logger.warning("Cleared all listening history")
