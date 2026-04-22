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
        timestamp: Optional[datetime] = None,
        skip_type: Optional[str] = None,
        percentage_played: Optional[float] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None
    ) -> Dict:
        """
        Log a track event (play or skip with timing info).
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
            album (str): Album name.
            duration (int): Duration in seconds (optional).
            timestamp (datetime, optional): When the event occurred. Defaults to now.
            skip_type (str, optional): Type of skip: 'immediate_skip', 'partial_skip', 
                                      'late_skip', or 'complete_listen'. If provided,
                                      event type becomes 'skip'.
            percentage_played (float, optional): Percentage of track played (0-100).
            started_at (datetime, optional): When the track started playing.
            ended_at (datetime, optional): When the skip/end occurred.
        
        Returns:
            dict: The event that was added.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Determine event type based on skip_type
        event_type = "skip" if skip_type else "play"
        
        event = {
            "type": event_type,
            "track": track,
            "artist": artist,
            "album": album,
            "duration": duration,
            "timestamp": timestamp.isoformat()
        }
        
        # Add skip-specific fields if provided
        if skip_type:
            event["skip_type"] = skip_type
            if percentage_played is not None:
                event["percentage_played"] = round(percentage_played, 1)
            if started_at:
                event["started_at"] = started_at.isoformat()
            if ended_at:
                event["ended_at"] = ended_at.isoformat()
        
        self.history.append(event)
        log_msg = f"Added {event_type} event: {track} by {artist}"
        if skip_type:
            log_msg += f" ({skip_type}: {percentage_played:.1f}%)"
        logger.debug(log_msg)
        
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
        Log a track skip event (deprecated - use add_track() with skip_type instead).
        
        This method is kept for backward compatibility. Use add_track() with
        skip_type parameter for better tracking of skip timing.
        
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
    
    def add_complete_listen(
        self,
        track: str,
        artist: str,
        album: str,
        duration: int = 0,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None
    ) -> Dict:
        """
        Log a track that was listened to completely (natural transition).
        
        Called by background polling thread when a track ends naturally
        (user didn't skip it, song just finished).
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
            album (str): Album name.
            duration (int): Duration in seconds.
            started_at (datetime, optional): When the track started playing.
            ended_at (datetime, optional): When the track ended.
        
        Returns:
            dict: The complete_listen event that was added.
        """
        return self.add_track(
            track=track,
            artist=artist,
            album=album,
            duration=duration,
            skip_type="complete_listen",
            percentage_played=100.0,
            started_at=started_at,
            ended_at=ended_at
        )
    
    def get_recent(self, limit: int = 50) -> List[Dict]:
        """
        Get most recent play events (including complete listens from polling).
        
        Args:
            limit (int): Maximum number of events to return.
        
        Returns:
            list of play/complete_listen event dicts, most recent first.
        """
        # Include both explicit plays and complete listens (natural track transitions)
        relevant = [
            e for e in self.history 
            if e.get("type") == "play" or e.get("skip_type") == "complete_listen"
        ]
        return relevant[-limit:][::-1]  # Most recent first
    
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
    
    def get_skip_signals(self) -> Dict[str, List[Dict]]:
        """
        Categorize skip events into preference signals.
        
        Returns:
            dict with keys:
                'positive': complete_listen + late_skip events (user enjoyed it)
                'neutral': partial_skip events (user was okay with it)
                'negative': immediate_skip events (user didn't like it)
        """
        signals = {
            'positive': [],
            'neutral': [],
            'negative': []
        }
        
        for event in self.history:
            skip_type = event.get("skip_type")
            
            if skip_type == "complete_listen" or skip_type == "late_skip":
                signals['positive'].append(event)
            elif skip_type == "partial_skip":
                signals['neutral'].append(event)
            elif skip_type == "immediate_skip":
                signals['negative'].append(event)
        
        return signals
    
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
