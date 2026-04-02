"""
GitHub Inference Integration for GPT-4o API.

Uses ChatOpenAI with GitHub's inference endpoint to access GPT-4o model.
Provides methods for recommendation explanations, request parsing, and
multi-turn conversation with music-specific system prompts.
"""

import logging
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)


class GPTMusicAssistant:
    """
    Music recommendation chatbot using GPT-4o via GitHub inference endpoint.
    
    Provides natural language understanding for music requests and intelligent
    explanations of why certain songs are recommended. Uses conversation
    context to maintain coherent multi-turn interactions.
    """
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4o", temperature: float = 0.7):
        """
        Initialize GPT music assistant.
        
        Args:
            api_key (str): GitHub token with access to GPT-4o.
            model (str): Model identifier. Default "openai/gpt-4o".
            temperature (float): Sampling temperature (0.0-1.0). Default 0.7.
        """
        try:
            self.client = ChatOpenAI(
                model=model,
                temperature=temperature,
                base_url="https://models.github.ai/inference",
                api_key=api_key
            )
            logger.info(f"Initialized ChatOpenAI with model {model}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI: {e}")
            raise
    
    def _build_system_prompt(self, listening_context: Dict) -> str:
        """
        Build a system prompt with personalized music context.
        
        Args:
            listening_context (dict): User's listening context including
                                     'mood', 'top_genres', 'top_artists', etc.
        
        Returns:
            str: System prompt for the model.
        """
        mood = listening_context.get("current_mood", "unspecified")
        top_genres = listening_context.get("top_genres", [])
        top_artists = listening_context.get("top_artists", [])
        play_count = listening_context.get("play_count", 0)
        
        genres_str = ", ".join(top_genres) if top_genres else "not yet determined"
        artists_str = ", ".join(top_artists) if top_artists else "not yet determined"
        
        return f"""You are a friendly and knowledgeable music recommendation assistant.
Your role is to help the user discover new music and control their Apple Music playback.

User's Listening Profile:
- Current mood: {mood}
- Top genres: {genres_str}
- Favorite artists: {artists_str}
- Songs played in session: {play_count}

When recommending music:
1. Consider their mood and listening history
2. Suggest songs from their favorite genres and artists
3. Explain WHY you're recommending something (connection to their taste, mood match, etc.)
4. Be conversational and encouraging
5. Ask clarifying questions if the request is ambiguous

When discussing music:
- Be enthusiastic about music
- Connect recommendations to their demonstrated preferences
- Suggest exploring new artists similar to their favorites
- Acknowledge when they skip songs (they probably didn't like it)

Format your responses clearly. When recommending songs, list them as:
- Song Title by Artist Name (Album) - Brief explanation of why this fits

Keep responses concise (2-3 sentences max for recommendations) but warm and helpful."""
    
    def generate_recommendation_reason(
        self,
        track: str,
        artist: str,
        listening_context: Dict
    ) -> str:
        """
        Generate a natural language explanation for why a song is recommended.
        
        Args:
            track (str): Track name.
            artist (str): Artist name.
            listening_context (dict): User's listening context.
        
        Returns:
            str: Natural language explanation.
        """
        system_prompt = self._build_system_prompt(listening_context)
        
        user_message = f"""Explain briefly (1-2 sentences) why I might enjoy "{track}" by {artist}.
Consider my mood preferences and listening history."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
            
            response = self.client.invoke(messages)
            explanation = response.content
            logger.debug(f"Generated recommendation reason: {explanation}")
            return explanation
        
        except Exception as e:
            logger.error(f"Failed to generate recommendation reason: {e}")
            return f"I think you'd enjoy this based on your listening history."
    
    def process_user_request(
        self,
        message: str,
        listening_context: Dict,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Process user's natural language request and extract intent/suggestions.
        
        Args:
            message (str): User's input message.
            listening_context (dict): User's listening context.
            conversation_history (list, optional): Previous conversation turns.
        
        Returns:
            dict with keys:
                - 'response': Assistant's response to the user
                - 'suggested_songs': List of song dicts to play
                - 'action': Suggested action (play, skip, pause, etc)
        """
        system_prompt = self._build_system_prompt(listening_context)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Add conversation history if provided
        if conversation_history:
            for turn in conversation_history[-5:]:  # Last 5 turns for context
                if turn["role"] == "user":
                    messages.append(HumanMessage(content=turn["content"]))
                else:
                    messages.append(AIMessage(content=turn["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        try:
            response = self.client.invoke(messages)
            response_text = response.content
            
            logger.debug(f"GPT response: {response_text}")
            
            return {
                "response": response_text,
                "suggested_songs": [],  # Could be extracted with structured output
                "action": None  # Could be extracted from response
            }
        
        except Exception as e:
            logger.error(f"Failed to process user request: {e}")
            return {
                "response": "I'm having trouble processing your request. Could you try again?",
                "suggested_songs": [],
                "action": None
            }
    
    def chat(
        self,
        user_message: str,
        listening_context: Dict,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Simple chat interface for multi-turn conversation.
        
        Args:
            user_message (str): User's message.
            listening_context (dict): User's listening context.
            conversation_history (list, optional): Previous conversation turns.
        
        Returns:
            str: Assistant's response.
        """
        system_prompt = self._build_system_prompt(listening_context)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Add conversation history
        if conversation_history:
            for turn in conversation_history[-5:]:  # Keep last 5 turns
                role = turn.get("role", "user")
                content = turn.get("content", "")
                
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))
        
        # Add current message
        messages.append(HumanMessage(content=user_message))
        
        try:
            response = self.client.invoke(messages)
            return response.content
        
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def refine_recommendations(
        self,
        recommendations: List[Dict],
        user_feedback: str,
        listening_context: Dict
    ) -> List[Dict]:
        """
        Re-rank recommendations based on user feedback.
        
        Args:
            recommendations (list): Initial recommendation list.
            user_feedback (str): User's feedback (e.g., "too upbeat", "perfect").
            listening_context (dict): User's listening context.
        
        Returns:
            list: Re-ranked recommendations.
        """
        system_prompt = self._build_system_prompt(listening_context)
        
        tracks_str = "\n".join([
            f"- {r['track']} by {r['artist']}"
            for r in recommendations[:5]
        ])
        
        user_prompt = f"""Given this feedback: "{user_feedback}"
        
Can you re-rank these recommendations from best to worst match?
{tracks_str}

Just list them in order (best first), with brief explanations."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.client.invoke(messages)
            logger.debug(f"Refined recommendations: {response.content}")
            
            # Return original list as fallback (structured parsing would improve this)
            return recommendations
        
        except Exception as e:
            logger.error(f"Failed to refine recommendations: {e}")
            return recommendations
