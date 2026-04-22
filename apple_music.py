"""
Apple Music integration layer using AppleScript.

This module provides safe wrappers around AppleScript commands to control
Apple Music playback and query library information. All AppleScript execution
is wrapped with proper error handling, timeouts, and logging.

Key limitations:
- AppleScript is single-threaded (operations are queued)
- Large library queries are slow (caching is recommended)
- Requires macOS with Apple Music app installed
"""

import subprocess
import json
import logging
import urllib.parse
import threading
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AppleScriptError(Exception):
    """Raised when AppleScript execution fails."""
    pass


class AppleMusicController:
    """
    Safe wrapper for Apple Music AppleScript operations.
    
    Provides methods to control playback (play, pause, skip) and query
    library information (current track, all songs, playlists).
    """
    
    def __init__(self, timeout: int = 10, listening_history=None, enable_polling: bool = True):
        """
        Initialize Apple Music controller.
        
        Args:
            timeout (int): Maximum seconds for AppleScript execution. Default 10s.
            listening_history: Optional ListeningHistory instance for auto-logging plays.
            enable_polling (bool): Whether to start background track polling thread. Default True.
        """
        self.timeout = timeout
        self.library_timeout = 180  # Separate, longer timeout for library operations (3 min for large libraries)
        self.listening_history = listening_history
        self._library_cache = None
        self._library_cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
        
        # Initialize polling thread if enabled
        self.poller = None
        if enable_polling and listening_history:
            self.poller = TrackPoller(self, listening_history)
            self.poller.start()
    
    def run_applescript(self, script: str, timeout: Optional[int] = None) -> str:
        """
        Execute AppleScript safely with error handling and timeout.
        
        Args:
            script (str): AppleScript code to execute.
            timeout (int, optional): Override default timeout in seconds.
        
        Returns:
            str: stdout from AppleScript execution (trimmed).
        
        Raises:
            AppleScriptError: If execution fails or times out.
        """
        _timeout = timeout if timeout is not None else self.timeout
        
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=_timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                raise AppleScriptError(f"AppleScript failed: {error_msg}")
            
            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            raise AppleScriptError(
                f"AppleScript execution timed out after {_timeout} seconds"
            )
        except FileNotFoundError:
            raise AppleScriptError(
                "osascript not found. This feature requires macOS."
            )
    
    def get_current_track(self) -> Optional[Dict[str, str]]:
        """
        Get currently playing track information.
        
        Returns:
            dict with keys 'track', 'artist', 'album', 'duration' if playing,
            or None if nothing is currently playing.
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        script = '''
        tell application "Music"
            if player state is playing then
                set current_track to current track
                set track_name to name of current_track
                set artist_name to artist of current_track
                set album_name to album of current_track
                set track_duration to duration of current_track
                return track_name & "|" & artist_name & "|" & album_name & "|" & track_duration
            else
                return ""
            end if
        end tell
        '''
        
        try:
            output = self.run_applescript(script)
            
            if not output:
                logger.debug("No track currently playing")
                return None
            
            parts = output.split("|")
            if len(parts) < 4:
                logger.warning(f"Unexpected output format: {output}")
                return None
            
            return {
                "track": parts[0],
                "artist": parts[1],
                "album": parts[2],
                "duration": parts[3]
            }
        except AppleScriptError as e:
            logger.error(f"Failed to get current track: {e}")
            raise
    
    def play_pause(self) -> str:
        """
        Toggle play/pause state.
        
        Returns:
            str: New player state ("playing" or "paused").
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        script = '''
        tell application "Music"
            playpause
            return player state
        end tell
        '''
        
        try:
            state = self.run_applescript(script)
            logger.info(f"Play/pause toggled. New state: {state}")
            return state
        except AppleScriptError as e:
            logger.error(f"Failed to toggle play/pause: {e}")
            raise
    
    def skip_track(self) -> Dict[str, str]:
        """
        Skip to next track.
        
        Automatically logs the current track as a skip with timing information
        (if polling thread is enabled).
        
        Returns:
            dict with keys 'track', 'artist', 'album' of new track.
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        # Log the current track as skipped with detailed timing info
        current = self.get_current_track()
        if current:
            if self.poller:
                # Use poller to log with elapsed time calculation
                self.poller.log_skip(current)
            elif self.listening_history:
                # Fallback: simple skip logging if polling disabled
                self.listening_history.add_skip(
                    current["track"],
                    current["artist"],
                    datetime.now()
                )
        
        script = '''
        tell application "Music"
            next track
            delay 0.5
            set current_track to current track
            set track_name to name of current_track
            set artist_name to artist of current_track
            set album_name to album of current_track
            return track_name & "|" & artist_name & "|" & album_name
        end tell
        '''
        
        try:
            output = self.run_applescript(script)
            parts = output.split("|")
            
            result = {
                "track": parts[0] if len(parts) > 0 else "Unknown",
                "artist": parts[1] if len(parts) > 1 else "Unknown",
                "album": parts[2] if len(parts) > 2 else "Unknown"
            }
            
            logger.info(f"Skipped to next track: {result['track']} by {result['artist']}")
            return result
        except AppleScriptError as e:
            logger.error(f"Failed to skip track: {e}")
            raise
    
    def play_song_by_name(self, song_name: str, artist: Optional[str] = None) -> Dict[str, str]:
        """
        Play a song by searching the library.
        
        Args:
            song_name (str): Name of song to search for.
            artist (str, optional): Artist name to filter results.
        
        Returns:
            dict with keys 'track', 'artist', 'album' of played song.
        
        Raises:
            AppleScriptError: If song not found or playback fails.
        
        Note:
            Due to Music app limitations with its search API (error -1708),
            we search Python-side using the cached library, then play via name match.
        """
        # First, search our Python-side library cache for the song
        matching_songs = []
        
        for song in self.library:
            if song_name.lower() in song.get("track", "").lower():
                if artist is None or artist.lower() in song.get("artist", "").lower():
                    matching_songs.append(song)
        
        if not matching_songs:
            raise AppleScriptError(f"Song '{song_name}' not found in library")
        
        # Use the first match
        target_song = matching_songs[0]
        
        # Now play via AppleScript using the track name directly
        # This avoids the search function's -1708 error
        play_script = f'''
        tell application "Music"
            set library_list to every track of library playlist 1
            set found to false
            
            repeat with aTrack in library_list
                if name of aTrack = "{target_song['track']}" and artist of aTrack = "{target_song['artist']}" then
                    play aTrack
                    set found to true
                    exit repeat
                end if
            end repeat
            
            if found then
                delay 0.5
                return (name of current track) & "|" & (artist of current track) & "|" & (album of current track)
            else
                return "NOT_FOUND"
            end if
        end tell
        '''
        
        try:
            # Use extended timeout since we might be iterating through many songs
            output = self.run_applescript(play_script, timeout=60)
            
            if output == "NOT_FOUND":
                raise AppleScriptError(f"Could not play: Match found in library but not in Music app")
            
            parts = output.split("|")
            result = {
                "track": parts[0] if len(parts) > 0 else target_song["track"],
                "artist": parts[1] if len(parts) > 1 else target_song["artist"],
                "album": parts[2] if len(parts) > 2 else target_song.get("album", "Unknown")
            }
            
            if output == "NOT_FOUND":
                raise AppleScriptError(f"Song '{song_name}' not found in library")
            
            parts = output.split("|")
            result = {
                "track": parts[0] if len(parts) > 0 else song_name,
                "artist": parts[1] if len(parts) > 1 else "Unknown",
                "album": parts[2] if len(parts) > 2 else "Unknown"
            }
            
            # Log the play event
            if self.listening_history:
                self.listening_history.add_track(
                    result["track"],
                    result["artist"],
                    result["album"],
                    duration=0,  # Duration not available here
                    timestamp=datetime.now()
                )
            
            logger.info(f"Now playing: {result['track']} by {result['artist']}")
            return result
        except AppleScriptError as e:
            logger.error(f"Failed to play song: {e}")
            raise
    
    def get_all_songs(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        Get all songs from library.
        
        WARNING: This is slow for large libraries (1000+ songs).
        Results are cached for 5 minutes by default.
        
        Args:
            use_cache (bool): Whether to use cached results if available.
        
        Returns:
            list of dicts with keys 'track', 'artist', 'album'.
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        # Check cache
        if use_cache and self._library_cache is not None:
            age = datetime.now() - self._library_cache_timestamp
            if age.total_seconds() < self._cache_ttl:
                logger.debug(f"Using cached library ({len(self._library_cache)} songs)")
                return self._library_cache
        
        logger.info("Querying full music library (this may take a moment)...")
        
        script = '''
        tell application "Music"
            set song_list to every track of library playlist 1
            set result_list to {}
            repeat with aTrack in song_list
                set track_name to name of aTrack
                set artist_name to artist of aTrack
                set album_name to album of aTrack
                set end of result_list to track_name & "||" & artist_name & "||" & album_name & linefeed
            end repeat
            return result_list as text
        end tell
        '''
        
        try:
            # Use longer timeout for library operations
            output = self.run_applescript(script, timeout=self.library_timeout)
            
            songs = []
            if output:
                for line in output.split("\n"):
                    line = line.strip()
                    if line:
                        parts = line.split("||")
                        if len(parts) >= 3:
                            songs.append({
                                "track": parts[0].strip(),
                                "artist": parts[1].strip(),
                                "album": parts[2].strip()
                            })
            
            # Cache the results
            self._library_cache = songs
            self._library_cache_timestamp = datetime.now()
            
            logger.info(f"Loaded {len(songs)} songs from library")
            return songs
        except AppleScriptError as e:
            logger.error(f"Failed to get all songs: {e}")
            raise
    
    def get_playlists(self) -> List[str]:
        """
        Get list of user's playlist names.
        
        Returns:
            list of playlist names (excluding Library, etc).
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        script = '''
        tell application "Music"
            set playlist_list to every user playlist
            set result_list to {}
            repeat with aPlaylist in playlist_list
                set end of result_list to name of aPlaylist
            end repeat
            return result_list as text
        end tell
        '''
        
        try:
            output = self.run_applescript(script)
            playlists = [p.strip() for p in output.split("\n") if p.strip()]
            logger.info(f"Found {len(playlists)} playlists")
            return playlists
        except AppleScriptError as e:
            logger.error(f"Failed to get playlists: {e}")
            raise
    
    def get_player_state(self) -> str:
        """
        Get current player state.
        
        Returns:
            str: "playing", "paused", or "stopped".
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        script = '''
        tell application "Music"
            return player state
        end tell
        '''
        
        try:
            state = self.run_applescript(script)
            return state.lower()
        except AppleScriptError as e:
            logger.error(f"Failed to get player state: {e}")
            raise
    
    def clear_cache(self):
        """Clear the library cache."""
        self._library_cache = None
        self._library_cache_timestamp = None
        logger.debug("Library cache cleared")
    
    def get_apple_music_search_url(self, song_name: str, artist: Optional[str] = None) -> str:
        """
        Generate an Apple Music search URL for a song.
        
        This creates a clickable link that opens Apple Music to search for the song.
        User can then stream, add to library, or view more info about the track.
        
        Args:
            song_name (str): Name of the song to search for.
            artist (str, optional): Artist name to include in search for better results.
        
        Returns:
            str: Apple Music search URL (https://music.apple.com/search?term=...)
        
        Example:
            >>> controller = AppleMusicController()
            >>> url = controller.get_apple_music_search_url("River", "Leon Bridges")
            >>> print(url)
            https://music.apple.com/search?term=River+Leon+Bridges
        """
        # Build search query
        search_query = song_name
        if artist:
            search_query = f"{song_name} {artist}"
        
        # URL encode the search query
        encoded_query = urllib.parse.quote(search_query)
        
        # Return Apple Music search URL
        return f"https://music.apple.com/search?term={encoded_query}"
    
    def shutdown(self):
        """Gracefully shutdown controller and cleanup resources."""
        if hasattr(self, 'poller') and self.poller:
            self.poller.stop()
            logger.debug("Stopped track polling thread")


class TrackPoller:
    """
    Background daemon thread that polls current track every N seconds
    and automatically logs complete song listens and skip events.
    
    Tracks elapsed time when songs are skipped to categorize skip intent:
    - immediate_skip (< 20%): User didn't like the song
    - partial_skip (20-80%): Song was okay but user wanted change  
    - late_skip (> 80%): User enjoyed it but wanted variety
    - complete_listen (100%): Track ended naturally (strong positive)
    """
    
    def __init__(
        self,
        apple_music_controller: AppleMusicController,
        listening_history,
        poll_interval: int = 5,
        skip_threshold_immediate: float = 0.20,
        skip_threshold_late: float = 0.80
    ):
        """
        Initialize background track poller.
        
        Args:
            apple_music_controller: AppleMusicController instance for getting current track
            listening_history: ListeningHistory instance for logging events
            poll_interval (int): Polling interval in seconds (default 5s)
            skip_threshold_immediate (float): Percentage (0-1) below which skip is "immediate"
            skip_threshold_late (float): Percentage (0-1) above which skip is "late"
        """
        self.controller = apple_music_controller
        self.history = listening_history
        self.poll_interval = poll_interval
        self.skip_threshold_immediate = skip_threshold_immediate
        self.skip_threshold_late = skip_threshold_late
        
        # Track state
        self.current_track = None
        self.track_started_at = None
        self.running = False
        self.thread = None
        
        logger.debug(f"TrackPoller initialized (interval={poll_interval}s)")
    
    def start(self):
        """Start background polling thread (daemon mode)."""
        if self.running:
            logger.warning("TrackPoller is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info("TrackPoller started")
    
    def stop(self):
        """Stop polling thread gracefully."""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("TrackPoller stopped")
    
    def _poll_loop(self):
        """Main polling loop (runs in background)."""
        while self.running:
            try:
                current = self.controller.get_current_track()
                
                # Track changed
                if current != self.current_track:
                    # Log previous track if it ended naturally
                    if self.current_track is not None:
                        self._log_complete_listen(
                            self.current_track,
                            self.track_started_at,
                            datetime.now()
                        )
                    
                    # Update to new track
                    self.current_track = current
                    self.track_started_at = datetime.now()
                    
                    if current:
                        logger.debug(f"Now polling: {current['track']} by {current['artist']}")
                
                time.sleep(self.poll_interval)
            
            except Exception as e:
                logger.error(f"Error in track polling loop: {e}")
                time.sleep(self.poll_interval)
    
    def log_skip(self, skipped_track: Dict) -> Dict:
        """
        Log a track skip with timing information.
        
        Called when user skips via CLI. Calculates elapsed time and categorizes
        skip intent (immediate/partial/late).
        
        Args:
            skipped_track (dict): Track info dict with 'track', 'artist', 'album', 'duration'
        
        Returns:
            dict: The skip event that was logged
        """
        if not self.track_started_at:
            logger.warning("No track start time - skipping logging")
            return {}
        
        # Calculate elapsed time and percentage
        elapsed = (datetime.now() - self.track_started_at).total_seconds()
        duration = float(skipped_track.get('duration', 0))
        
        if duration <= 0:
            percentage = 50  # Fallback if no duration available
        else:
            percentage = min(100, (elapsed / duration) * 100)
        
        # Categorize skip based on percentage
        if percentage < self.skip_threshold_immediate * 100:
            skip_type = "immediate_skip"
        elif percentage > self.skip_threshold_late * 100:
            skip_type = "late_skip"
        else:
            skip_type = "partial_skip"
        
        # Log with detailed timing info
        event = self.history.add_track(
            track=skipped_track['track'],
            artist=skipped_track['artist'],
            album=skipped_track.get('album', 'Unknown'),
            duration=duration,
            skip_type=skip_type,
            percentage_played=percentage,
            started_at=self.track_started_at,
            ended_at=datetime.now()
        )
        
        logger.debug(f"Logged skip: {skip_type} ({percentage:.1f}%) - {skipped_track['track']}")
        
        # Reset for next track
        self.current_track = None
        self.track_started_at = None
        
        return event
    
    def _log_complete_listen(
        self,
        track: Dict,
        started: datetime,
        ended: datetime
    ) -> Dict:
        """
        Log a track that was listened to completely (natural transition).
        
        Called automatically when track changes without user skipping.
        
        Args:
            track (dict): Track info dict
            started (datetime): When track started
            ended (datetime): When track ended
        
        Returns:
            dict: The complete_listen event that was logged
        """
        event = self.history.add_complete_listen(
            track=track['track'],
            artist=track['artist'],
            album=track.get('album', 'Unknown'),
            duration=float(track.get('duration', 0)),
            started_at=started,
            ended_at=ended
        )
        
        logger.debug(f"Logged complete listen: {track['track']} by {track['artist']}")
        return event
