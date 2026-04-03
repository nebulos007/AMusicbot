"""
Apple Music MCP Server - Main orchestrator.

Exposes Apple Music playback control and intelligent music recommendation
capabilities through the Model Context Protocol (MCP). Tools include playback
control (play/pause/skip), library search, recommendations, and natural
language chat with GPT-4o.

Architecture:
- AppleMusicController: Communicates with Apple Music via AppleScript
- MusicChatSession: Maintains conversation context and intent detection
- MusicRecommender: Generates personalized recommendations
- ListeningHistory: Tracks plays/skips for preference learning
- GPTMusicAssistant: Natural language understanding via GPT-4o
"""

import logging
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from apple_music import AppleMusicController, AppleScriptError
from chat_manager import MusicChatSession, UserIntent
from recommender import MusicRecommender
from listening_history import ListeningHistory
from library_cache import LibraryCache
from utils.gpt_integration import GPTMusicAssistant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("Apple Music Bot", json_response=True)

# Global components (initialized on startup)
apple_music: Optional[AppleMusicController] = None
chat_session: Optional[MusicChatSession] = None
recommender: Optional[MusicRecommender] = None
listening_history: Optional[ListeningHistory] = None
library_cache: Optional[LibraryCache] = None
gpt_assistant: Optional[GPTMusicAssistant] = None


def initialize_components():
    """Initialize all server components."""
    global apple_music, chat_session, recommender, listening_history, library_cache, gpt_assistant
    
    logger.info("Initializing Apple Music MCP Server components...")
    
    # Initialize listening history (loads from file if available)
    listening_history = ListeningHistory("listening_history.json")
    
    # Initialize library cache
    library_cache = LibraryCache("library_cache.json")
    
    # Initialize Apple Music controller
    apple_music = AppleMusicController(listening_history=listening_history)
    
    # Try to load initial listening history from Apple Music
    try:
        apple_music.get_current_track()  # Test connection
        listening_history.load_initial_from_applescript(apple_music)
        logger.info("Successfully connected to Apple Music")
    except AppleScriptError as e:
        logger.warning(f"Could not connect to Apple Music: {e}")
    
    # Initialize chat session
    chat_session = MusicChatSession("default")
    
    # Initialize recommender with library data
    recommender = MusicRecommender()
    
    # Load library (try cache first, then Apple Music)
    library = []
    if library_cache.load_from_cache():
        library = library_cache.get_library()
        recommender.load_library(library)
    else:
        logger.info("Building library cache (first run may take a while for large libraries)...")
        try:
            library = apple_music.get_all_songs()
            library_cache.save_to_cache(library)
            recommender.load_library(library)
            logger.info(f"Loaded and cached {len(library)} songs")
        except AppleScriptError as e:
            logger.warning(f"Could not load library (will use recommendations without library): {e}")
    
    # Load listening history into recommender
    recent_plays = listening_history.get_recent(limit=100)
    recommender.load_listening_history(recent_plays)
    
    # Initialize GPT assistant
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN not found in environment. Please set it in .env file.")
    
    gpt_assistant = GPTMusicAssistant(api_key=github_token)
    
    logger.info("✅ All components initialized successfully")


# ============================================================================
# PLAYBACK CONTROL TOOLS
# ============================================================================

@mcp.tool()
def get_current_track() -> Dict[str, Any]:
    """
    Get the currently playing track information.
    
    Returns:
        dict with track name, artist, album, and duration.
        Returns {"status": "stopped"} if nothing is playing.
    """
    try:
        current = apple_music.get_current_track()
        if current:
            return current
        return {"status": "stopped"}
    except AppleScriptError as e:
        return {"error": str(e), "status": "error"}


@mcp.tool()
def play_pause() -> Dict[str, str]:
    """
    Toggle play/pause state.
    
    Returns:
        dict with new player state ("playing" or "paused").
    """
    try:
        state = apple_music.play_pause()
        return {"state": state}
    except AppleScriptError as e:
        return {"error": str(e)}


@mcp.tool()
def skip_track() -> Dict[str, str]:
    """
    Skip to next track.
    
    Returns:
        dict with new track name, artist, and album.
    """
    try:
        result = apple_music.skip_track()
        chat_session.update_context("current_track", result)
        return result
    except AppleScriptError as e:
        return {"error": str(e)}


@mcp.tool()
def get_player_state() -> Dict[str, str]:
    """
    Get current player state without changing it.
    
    Returns:
        dict with player state ("playing", "paused", or "stopped").
    """
    try:
        state = apple_music.get_player_state()
        return {"state": state}
    except AppleScriptError as e:
        return {"error": str(e)}


# ============================================================================
# SEARCH AND PLAYBACK TOOLS
# ============================================================================

@mcp.tool()
def search_and_play(song_name: str, artist: Optional[str] = None) -> Dict[str, Any]:
    """
    Search library for a song and play it.
    
    Args:
        song_name: Name of the song to search for.
        artist: Optional artist name to filter results.
    
    Returns:
        dict with played track info or error message.
    """
    try:
        result = apple_music.play_song_by_name(song_name, artist)
        chat_session.update_context("current_track", result)
        
        # Log to listening history
        listening_history.add_track(
            result["track"],
            result["artist"],
            result.get("album", "Unknown")
        )
        
        return result
    except AppleScriptError as e:
        return {"error": str(e)}


# ============================================================================
# LIBRARY AND DISCOVERY TOOLS
# ============================================================================

@mcp.tool()
def get_all_songs() -> Dict[str, Any]:
    """
    Get all songs from library.
    
    WARNING: This is slow for large libraries. Results are cached.
    
    Returns:
        dict with song list and count.
    """
    try:
        songs = apple_music.get_all_songs()
        return {"count": len(songs), "songs": songs[:20]}  # Return first 20 + count
    except AppleScriptError as e:
        return {"error": str(e)}


@mcp.tool()
def get_playlists() -> Dict[str, Any]:
    """
    Get list of user's playlists.
    
    Returns:
        dict with list of playlist names.
    """
    try:
        playlists = apple_music.get_playlists()
        return {"count": len(playlists), "playlists": playlists}
    except AppleScriptError as e:
        return {"error": str(e)}


# ============================================================================
# RECOMMENDATION TOOLS
# ============================================================================

@mcp.tool()
def get_recommendations(mood: Optional[str] = None, count: int = 10) -> Dict[str, Any]:
    """
    Get personalized music recommendations.
    
    Args:
        mood: Optional mood for recommendation (e.g., "chill", "energetic").
        count: Number of recommendations (default 10, max 20).
    
    Returns:
        dict with list of recommended tracks and reasons.
    """
    count = min(count, 20)  # Cap at 20
    
    context = chat_session.context.copy()
    if mood:
        context["current_mood"] = mood
    
    try:
        recommendations = recommender.get_recommendations(context, count)
        
        # Enrich with GPT explanations for top recommendations
        enriched = []
        for rec in recommendations[:3]:  # Top 3 explanations from GPT
            try:
                explanation = gpt_assistant.generate_recommendation_reason(
                    rec["track"],
                    rec["artist"],
                    context
                )
                rec["gpt_reason"] = explanation
            except Exception as e:
                logger.warning(f"Failed to get GPT explanation: {e}")
                rec["gpt_reason"] = rec.get("reason", "Personalized for you")
            
            enriched.append(rec)
        
        # Add rest without enrichment
        enriched.extend(recommendations[3:])
        
        return {"count": len(enriched), "recommendations": enriched}
    
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def recommend_by_mood(mood: str, count: int = 10) -> Dict[str, Any]:
    """
    Get recommendations based on mood.
    
    Args:
        mood: Mood keyword (chill, energetic, relaxing, upbeat, focus, etc).
        count: Number of recommendations (default 10, max 20).
    
    Returns:
        dict with mood-matched recommendations.
    """
    count = min(count, 20)
    
    try:
        recommendations = recommender.recommend_by_mood(mood, count)
        return {"mood": mood, "count": len(recommendations), "recommendations": recommendations}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def recommend_by_artist(artist: str, count: int = 10) -> Dict[str, Any]:
    """
    Get recommendations based on a reference artist.
    
    Args:
        artist: Artist name to base recommendations on.
        count: Number of recommendations (default 10, max 20).
    
    Returns:
        dict with similar artist recommendations.
    """
    count = min(count, 20)
    
    try:
        recommendations = recommender.recommend_by_artist(artist, count)
        return {
            "reference_artist": artist,
            "count": len(recommendations),
            "recommendations": recommendations
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# CHAT AND INTELLIGENCE TOOLS
# ============================================================================

@mcp.tool()
def chat(user_message: str) -> Dict[str, Any]:
    """
    Chat with the music recommendation assistant.
    
    Processes natural language requests, detects intent, and provides
    contextual responses about music recommendations and playback.
    
    Args:
        user_message: User's natural language input.
    
    Returns:
        dict with:
            - response: Assistant's text response
            - detected_intent: Intent extracted from message
            - suggested_action: Recommended action (if any)
    """
    try:
        # Process input through chat manager
        processed = chat_session.process_user_input(user_message)
        intent = processed["intent"]
        entities = processed["entities"]
        
        # Get conversation context
        history = chat_session.get_context_window(num_turns=5)
        listening_context = chat_session.context.copy()
        
        # Update listening context with recommender insights
        preferences = recommender.get_preference_summary()
        listening_context.update({
            "top_genres": preferences.get("top_genres", []),
            "top_artists": preferences.get("top_artists", []),
            "play_count": listening_history.get_play_count()
        })
        
        # Get GPT response
        gpt_response = gpt_assistant.chat(user_message, listening_context, history)
        
        # Add to chat history
        chat_session.add_assistant_response(gpt_response)
        
        # Determine action based on intent
        action = None
        action_result = None
        
        if intent == UserIntent.PLAY and "song" in entities:
            try:
                action = "play"
                action_result = search_and_play(
                    entities["song"],
                    entities.get("artist")
                )
            except Exception as e:
                logger.warning(f"Failed to play song: {e}")
        
        elif intent == UserIntent.RECOMMEND:
            mood = entities.get("mood")
            action = "recommend"
            action_result = get_recommendations(mood=mood, count=5)
        
        elif intent == UserIntent.SKIP:
            action = "skip"
            action_result = skip_track()
        
        elif intent == UserIntent.PAUSE:
            action = "pause"
            action_result = play_pause()
        
        return {
            "response": gpt_response,
            "detected_intent": intent.value,
            "entities": entities,
            "suggested_action": action,
            "action_result": action_result
        }
    
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "response": f"I encountered an error: {str(e)}",
            "error": str(e)
        }


# ============================================================================
# INFORMATION TOOLS
# ============================================================================

@mcp.tool()
def get_session_info() -> Dict[str, Any]:
    """
    Get session information and statistics.
    
    Returns:
        dict with listening history stats and preferences.
    """
    try:
        history_summary = listening_history.get_summary()
        preferences = recommender.get_preference_summary()
        chat_summary = chat_session.get_summary()
        
        return {
            "listening_history": history_summary,
            "preferences": preferences,
            "chat_session": chat_summary
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_listening_history(limit: int = 20) -> Dict[str, Any]:
    """
    Get recent listening history.
    
    Args:
        limit: Number of recent plays to return (max 50).
    
    Returns:
        dict with recent play events.
    """
    limit = min(limit, 50)
    
    try:
        recent = listening_history.get_recent(limit=limit)
        return {"count": len(recent), "recent_plays": recent}
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# RESOURCES (Data endpoints for LLM context)
# ============================================================================

@mcp.resource("music://library")
def get_library_resource() -> str:
    """
    Music library resource exposing song collection.
    
    Returns:
        JSON string with library information.
    """
    try:
        songs = apple_music.get_all_songs()
        return f"Library contains {len(songs)} songs"
    except AppleScriptError as e:
        return f"Error accessing library: {e}"


@mcp.resource("music://current")
def get_current_resource() -> str:
    """
    Current playback state resource.
    
    Returns:
        String describing what's currently playing.
    """
    try:
        current = apple_music.get_current_track()
        if current:
            return f"Now playing: {current['track']} by {current['artist']}"
        return "Nothing currently playing"
    except AppleScriptError as e:
        return f"Error getting current track: {e}"


@mcp.resource("music://history")
def get_history_resource() -> str:
    """
    Listening history resource.
    
    Returns:
        Summary of recent listening activity.
    """
    summary = listening_history.get_summary()
    return f"Session plays: {summary.get('total_plays', 0)}, Skips: {summary.get('total_skips', 0)}"


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================

if __name__ == "__main__":
    """Start the MCP server."""
    try:
        logger.info("Starting Apple Music MCP Server...")
        initialize_components()
        
        logger.info("🎵 MCP Server ready! Listening for connections...")
        mcp.run(transport="stdio")
    
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
