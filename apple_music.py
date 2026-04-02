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
    
    def __init__(self, timeout: int = 10, listening_history=None):
        """
        Initialize Apple Music controller.
        
        Args:
            timeout (int): Maximum seconds for AppleScript execution. Default 10s.
            listening_history: Optional ListeningHistory instance for auto-logging plays.
        """
        self.timeout = timeout
        self.listening_history = listening_history
        self._library_cache = None
        self._library_cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
    
    def run_applescript(self, script: str) -> str:
        """
        Execute AppleScript safely with error handling and timeout.
        
        Args:
            script (str): AppleScript code to execute.
        
        Returns:
            str: stdout from AppleScript execution (trimmed).
        
        Raises:
            AppleScriptError: If execution fails or times out.
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                raise AppleScriptError(f"AppleScript failed: {error_msg}")
            
            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            raise AppleScriptError(
                f"AppleScript execution timed out after {self.timeout} seconds"
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
        
        Returns:
            dict with keys 'track', 'artist', 'album' of new track.
        
        Raises:
            AppleScriptError: If AppleScript execution fails.
        """
        # Log the current track as skipped before moving to next
        current = self.get_current_track()
        if current and self.listening_history:
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
        Search library for a song and play it.
        
        Args:
            song_name (str): Name of song to search for.
            artist (str, optional): Artist name to filter results.
        
        Returns:
            dict with keys 'track', 'artist', 'album' of played song.
        
        Raises:
            AppleScriptError: If song not found or AppleScript fails.
        """
        # Build search script
        if artist:
            script = f'''
            tell application "Music"
                search for "{song_name}" only tracks
                set search_results to search results
                if (count of search_results) > 0 then
                    repeat with aTrack in search_results
                        if artist of aTrack contains "{artist}" then
                            play aTrack
                            delay 0.5
                            return (name of aTrack) & "|" & (artist of aTrack) & "|" & (album of aTrack)
                        end if
                    end repeat
                    -- If artist not found, play first result
                    play item 1 of search_results
                    set played_track to item 1 of search_results
                    return (name of played_track) & "|" & (artist of played_track) & "|" & (album of played_track)
                else
                    return "NOT_FOUND"
                end if
            end tell
            '''
        else:
            script = f'''
            tell application "Music"
                search for "{song_name}" only tracks
                set search_results to search results
                if (count of search_results) > 0 then
                    play item 1 of search_results
                    set played_track to item 1 of search_results
                    return (name of played_track) & "|" & (artist of played_track) & "|" & (album of played_track)
                else
                    return "NOT_FOUND"
                end if
            end tell
            '''
        
        try:
            output = self.run_applescript(script)
            
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
                set end of result_list to track_name & "||" & artist_name & "||" & album_name
            end repeat
            return result_list as text
        end tell
        '''
        
        try:
            output = self.run_applescript(script)
            
            songs = []
            if output:
                for line in output.split("\n"):
                    if line.strip():
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
