"""
Conversation management and intent detection for music chatbot.

This module maintains conversation context across multiple turns and extracts
user intent from natural language input. It tracks mood, listening history,
and conversation state to enable contextual responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class UserIntent(str, Enum):
    """Enumeration of recognized user intents."""
    PLAY = "play"
    PAUSE = "pause"
    SKIP = "skip"
    RECOMMEND = "recommend"
    SEARCH = "search"
    PLAYLIST = "playlist"
    EXPLAIN = "explain"
    CURRENT = "current"
    UNKNOWN = "unknown"


@dataclass
class Message:
    """Single message in conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    intent: Optional[UserIntent] = None
    entities: Dict[str, Any] = field(default_factory=dict)


class MusicChatSession:
    """
    Manages multi-turn conversation with music chatbot.
    
    Maintains message history, extracts user intent and entities,
    tracks conversation context (mood, listening patterns, preferences).
    """
    
    # Intent detection keywords
    INTENT_KEYWORDS = {
        UserIntent.PLAY: ["play", "start", "begin", "turn on", "play music"],
        UserIntent.PAUSE: ["pause", "stop", "hold on", "quiet"],
        UserIntent.SKIP: ["skip", "next", "forward", "different song"],
        UserIntent.RECOMMEND: ["recommend", "suggest", "what should", "what can", "play something"],
        UserIntent.SEARCH: ["find", "search", "look for", "where is"],
        UserIntent.PLAYLIST: ["playlist", "create playlist", "add to playlist"],
        UserIntent.EXPLAIN: ["why", "explain", "tell me about"],
        UserIntent.CURRENT: ["current", "now playing", "what is playing", "what song"],
    }
    
    def __init__(self, user_id: str = "default", max_history: int = 20):
        """
        Initialize chat session.
        
        Args:
            user_id (str): Unique identifier for this user session.
            max_history (int): Maximum messages to keep in history.
        """
        self.user_id = user_id
        self.messages: List[Message] = []
        self.max_history = max_history
        
        # Conversation context
        self.context = {
            "current_mood": None,
            "listening_history": [],
            "recent_skips": [],
            "preferences": {},
            "current_track": None,
            "session_start": datetime.now()
        }
    
    def add_message(
        self,
        role: str,
        content: str,
        intent: Optional[UserIntent] = None,
        entities: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add message to conversation history.
        
        Automatically trims old messages to maintain max_history limit.
        
        Args:
            role (str): "user" or "assistant".
            content (str): Message content.
            intent (UserIntent, optional): Detected user intent.
            entities (dict, optional): Extracted entities.
        
        Returns:
            Message: The message that was added.
        """
        message = Message(
            role=role,
            content=content,
            intent=intent,
            entities=entities or {}
        )
        self.messages.append(message)
        
        # Trim old messages
        if len(self.messages) > self.max_history:
            removed = self.messages.pop(0)
            logger.debug(f"Removed oldest message to maintain history limit")
        
        return message
    
    def extract_intent(self, user_input: str) -> tuple[UserIntent, Dict[str, Any]]:
        """
        Extract user intent and entities from natural language input.
        
        Uses keyword matching for initial intent detection, then extracts
        relevant entities (artist, song, mood, etc).
        
        Args:
            user_input (str): User's natural language input.
        
        Returns:
            tuple: (UserIntent, dict of extracted entities).
        """
        lower_input = user_input.lower()
        entities = {}
        
        # Detect intent by keyword matching
        detected_intent = UserIntent.UNKNOWN
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(keyword in lower_input for keyword in keywords):
                detected_intent = intent
                break
        
        # Extract entities based on intent
        if detected_intent == UserIntent.PLAY:
            # Extract song or artist name
            match = re.search(r'play (?:something |a |)?(.+?)(?:\s+by\s+(.+)|$)', lower_input)
            if match:
                entities["song"] = match.group(1).strip()
                if match.group(2):
                    entities["artist"] = match.group(2).strip()
        
        elif detected_intent == UserIntent.RECOMMEND:
            # Extract mood keywords
            mood_keywords = ["chill", "relaxing", "upbeat", "energetic", "sad", "happy",
                            "workout", "party", "focus", "sleep", "study", "romantic"]
            for mood in mood_keywords:
                if mood in lower_input:
                    entities["mood"] = mood
                    break
            
            # Extract artist or genre preferences
            if "like" in lower_input or "similar to" in lower_input:
                match = re.search(r'(?:like|similar to) (.+?)(?:\s+and|\s+or|$)', lower_input)
                if match:
                    entities["reference"] = match.group(1).strip()
        
        elif detected_intent == UserIntent.SEARCH:
            # Extract search query
            match = re.search(r'(?:find|search|look for) (.+?)(?:\s+by|$)', lower_input)
            if match:
                entities["query"] = match.group(1).strip()
        
        logger.debug(f"Extracted intent={detected_intent}, entities={entities}")
        return detected_intent, entities
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input: extract intent, update context, return structured data.
        
        This is the main entry point for handling user messages.
        
        Args:
            user_input (str): Raw user input.
        
        Returns:
            dict with keys:
                - 'intent': UserIntent
                - 'entities': Dict of extracted entities
                - 'context': Current conversation context
                - 'message': Message object that was added
        """
        # Extract intent and entities
        intent, entities = self.extract_intent(user_input)
        
        # Add to message history
        message = self.add_message("user", user_input, intent, entities)
        
        # Update context based on intent and entities
        if "mood" in entities:
            self.context["current_mood"] = entities["mood"]
        
        return {
            "intent": intent,
            "entities": entities,
            "context": self.context.copy(),
            "message": message
        }
    
    def add_assistant_response(self, response: str) -> Message:
        """
        Add assistant's response to conversation history.
        
        Args:
            response (str): Assistant's message.
        
        Returns:
            Message: The response message.
        """
        return self.add_message("assistant", response)
    
    def update_context(self, key: str, value: Any):
        """
        Update session context.
        
        Args:
            key (str): Context key ("current_mood", "current_track", etc).
            value: New value.
        """
        if key == "current_track":
            self.context["current_track"] = value
            # Add to listening history if it's a dict
            if isinstance(value, dict) and value not in self.context["listening_history"]:
                self.context["listening_history"].append(value)
        elif key == "mood":
            self.context["current_mood"] = value
        elif key == "skip":
            if isinstance(value, dict) and value not in self.context["recent_skips"]:
                self.context["recent_skips"].append(value)
        else:
            self.context[key] = value
        
        logger.debug(f"Updated context: {key}={value}")
    
    def get_context_window(self, num_turns: int = 10) -> List[Dict[str, str]]:
        """
        Get recent conversation context formatted for LLM.
        
        Args:
            num_turns (int): Number of recent turns to include.
        
        Returns:
            list of dicts with 'role' and 'content' keys.
        """
        recent_messages = self.messages[-num_turns:]
        return [
            {"role": m.role, "content": m.content}
            for m in recent_messages
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of conversation and context for LLM system prompt.
        
        Returns:
            dict with summary information about this session.
        """
        total_messages = len(self.messages)
        user_messages = sum(1 for m in self.messages if m.role == "user")
        
        return {
            "user_id": self.user_id,
            "total_messages": total_messages,
            "user_messages": user_messages,
            "current_mood": self.context["current_mood"],
            "current_track": self.context["current_track"],
            "tracks_played": len(self.context["listening_history"]),
            "skips": len(self.context["recent_skips"]),
            "session_duration": (datetime.now() - self.context["session_start"]).total_seconds()
        }
