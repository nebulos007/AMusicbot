"""
Music library caching with persistent JSON storage.

Caches the full music library after first load so subsequent startups
are instant. Useful for large libraries (2000+ songs) where AppleScript
queries take a very long time.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LibraryCache:
    """
    Manages caching of music library to JSON file.
    
    On first run: Loads library from Apple Music (may be slow for large libraries)
    On subsequent runs: Loads instantly from cache JSON file
    """
    
    def __init__(self, cache_file: str = "library_cache.json"):
        """
        Initialize library cache manager.
        
        Args:
            cache_file (str): Path to JSON file for caching.
        """
        self.cache_file = Path(cache_file)
        self.library: List[Dict] = []
        self.is_loaded = False
    
    def load_from_cache(self) -> bool:
        """
        Load library from cache file if it exists.
        
        Returns:
            bool: True if cache was loaded, False if cache doesn't exist.
        """
        if not self.cache_file.exists():
            logger.debug(f"No library cache found at {self.cache_file}")
            return False
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self.library = data.get("songs", [])
                self.is_loaded = True
                
                timestamp = data.get("cached_at", "unknown")
                logger.info(f"✅ Loaded {len(self.library)} songs from cache (cached at {timestamp})")
                return True
        
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load library cache: {e}")
            return False
    
    def save_to_cache(self, library: List[Dict]) -> bool:
        """
        Save library to cache file.
        
        Args:
            library (list): List of songs with 'track', 'artist', 'album' keys.
        
        Returns:
            bool: True if successfully saved.
        """
        try:
            data = {
                "songs": library,
                "cached_at": datetime.now().isoformat(),
                "song_count": len(library)
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.library = library
            self.is_loaded = True
            logger.info(f"✅ Cached {len(library)} songs to {self.cache_file}")
            return True
        
        except IOError as e:
            logger.error(f"Failed to save library cache: {e}")
            return False
    
    def get_library(self) -> List[Dict]:
        """
        Get cached library.
        
        Returns:
            list: Cached songs.
        """
        return self.library.copy()
    
    def clear_cache(self) -> bool:
        """
        Delete cache file.
        
        WARNING: This is destructive. Cache will need to be rebuilt.
        
        Returns:
            bool: True if cache was deleted.
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                self.library = []
                self.is_loaded = False
                logger.info(f"Cleared library cache")
                return True
            return False
        except IOError as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_cache_info(self) -> Dict:
        """
        Get information about the cache.
        
        Returns:
            dict with cache status and metadata.
        """
        exists = self.cache_file.exists()
        size = 0
        modified = None
        
        if exists:
            size = self.cache_file.stat().st_size
            modified = datetime.fromtimestamp(self.cache_file.stat().st_mtime).isoformat()
        
        return {
            "exists": exists,
            "path": str(self.cache_file),
            "size_bytes": size,
            "song_count": len(self.library),
            "last_modified": modified,
            "is_loaded": self.is_loaded
        }
