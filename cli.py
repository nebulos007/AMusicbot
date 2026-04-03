"""
Apple Music Chatbot CLI Interface.

Interactive command-line interface for the music recommendation chatbot.
Provides user-friendly interaction with playback control, recommendations,
and natural language chat with the assistant.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from apple_music import AppleMusicController, AppleScriptError
from chat_manager import MusicChatSession, UserIntent
from recommender import MusicRecommender
from listening_history import ListeningHistory
from library_cache import LibraryCache
from utils.gpt_integration import GPTMusicAssistant

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Less verbose for CLI
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AppleMusicCLI:
    """
    Interactive CLI for Apple Music chatbot.
    
    Provides a user-friendly command-line interface with features like:
    - Natural language music recommendations
    - Playback control (play, pause, skip)
    - Current track display
    - Command shortcuts for common actions
    """
    
    # Command shortcuts
    COMMANDS = {
        "/play": "Search and play a song",
        "/skip": "Skip current track",
        "/pause": "Pause/resume playback",
        "/current": "Show currently playing track",
        "/recommend": "Get personalized recommendations",
        "/mood": "Get recommendations for a specific mood",
        "/rebuild_library": "Rebuild library cache (takes 2-3 min, only needed if you added songs)",
        "/cache_info": "Show library cache information",
        "/history": "Show listening history",
        "/status": "Show session status",
        "/help": "Show this help message",
        "/quit": "Exit the application"
    }
    
    def __init__(self):
        """Initialize the CLI."""
        # Load environment
        load_dotenv()
        
        # Initialize components
        self.listening_history = ListeningHistory("listening_history.json")
        self.library_cache = LibraryCache("library_cache.json")
        self.apple_music = AppleMusicController(listening_history=self.listening_history)
        self.chat_session = MusicChatSession("cli_user")
        
        # Initialize GPT assistant first (before recommender)
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            raise ValueError("GITHUB_TOKEN not found in .env")
        self.gpt_assistant = GPTMusicAssistant(api_key=github_token)
        
        # Initialize recommender with GPT assistant for discovery recommendations
        self.recommender = MusicRecommender(gpt_assistant=self.gpt_assistant)
        
        # Load data
        self._initialize_data()
        
        self.running = True
    
    def _initialize_data(self):
        """Initialize data from Apple Music and files."""
        print(f"{Colors.CYAN}⏳ Loading music library...{Colors.END}")
        
        try:
            # Test connection
            self.apple_music.get_current_track()
            print(f"{Colors.GREEN}✅ Connection to Apple Music established{Colors.END}")
        except AppleScriptError as e:
            print(f"{Colors.YELLOW}⚠️  Could not connect to Apple Music: {e}{Colors.END}")
        
        # Try to load library from cache first
        library = []
        if self.library_cache.load_from_cache():
            library = self.library_cache.get_library()
            self.apple_music.library = library  # Load into AppleMusic controller for play_song_by_name
            self.recommender.load_library(library)
        else:
            # No cache - load from Apple Music (may be slow for large libraries)
            print(f"{Colors.CYAN}⏳ First run: Building library cache...{Colors.END}")
            print(f"{Colors.YELLOW}⚠️  This may take 2-3 minutes for large libraries. Please wait...{Colors.END}")
            try:
                library = self.apple_music.get_all_songs()
                self.library_cache.save_to_cache(library)
                self.apple_music.library = library  # Update AppleMusic controller with new library
                self.recommender.load_library(library)
                print(f"{Colors.GREEN}✅ Loaded and cached {len(library)} songs{Colors.END}")
            except AppleScriptError as e:
                print(f"{Colors.RED}❌ Library load failed: {e}{Colors.END}")
                print(f"{Colors.CYAN}💡 The chatbot will work with other features (playback, history).{Colors.END}")
                print(f"{Colors.CYAN}   Try /rebuild_library later when you have more time.{Colors.END}")
        
        # Load listening history
        recent_plays = self.listening_history.get_recent(limit=100)
        self.recommender.load_listening_history(recent_plays)
        print(f"{Colors.GREEN}✅ Loaded {len(recent_plays)} play events{Colors.END}\n")
    
    def print_header(self):
        """Print the CLI header."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}")
        print("🎵 Apple Music AI Chatbot 🎵")
        print(f"{Colors.END}{Colors.CYAN}Type /help for commands, or chat naturally with the bot!{Colors.END}\n")
    
    def show_help(self):
        """Display help message with available commands."""
        print(f"\n{Colors.BOLD}Available Commands:{Colors.END}")
        for cmd, desc in self.COMMANDS.items():
            print(f"  {Colors.CYAN}{cmd:<15}{Colors.END} {desc}")
        print()
    
    def show_current_track(self):
        """Display currently playing track."""
        try:
            current = self.apple_music.get_current_track()
            if current:
                print(f"{Colors.GREEN}🎵 Now playing:{Colors.END}")
                print(f"   Track:  {Colors.BOLD}{current['track']}{Colors.END}")
                print(f"   Artist: {current['artist']}")
                print(f"   Album:  {current['album']}")
            else:
                print(f"{Colors.YELLOW}⏸️  Nothing currently playing{Colors.END}")
        except AppleScriptError as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
    
    def show_status(self):
        """Display session status and statistics."""
        try:
            history_summary = self.listening_history.get_summary()
            prefs = self.recommender.get_preference_summary()
            chat_summary = self.chat_session.get_summary()
            
            print(f"\n{Colors.BOLD}Session Status:{Colors.END}")
            print(f"  Messages:       {chat_summary['total_messages']}")
            print(f"  Plays in session: {history_summary['total_plays']}")
            print(f"  Skips in session: {history_summary['total_skips']}")
            print(f"  Unique artists: {prefs['unique_artists']}")
            print(f"  Top genres:     {', '.join(prefs['top_genres'][:3]) if prefs['top_genres'] else 'None yet'}")
            print()
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
    
    def show_history(self, limit: int = 10):
        """Display recent listening history."""
        try:
            recent = self.listening_history.get_recent(limit=limit)
            if not recent:
                print(f"{Colors.YELLOW}No listening history yet{Colors.END}")
                return
            
            print(f"\n{Colors.BOLD}Recent Plays (last {limit}):{Colors.END}")
            for i, event in enumerate(recent, 1):
                print(f"  {i}. {event['track']} - {event['artist']}")
            print()
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
    
    def get_recommendations(self, mood: Optional[str] = None):
        """Display recommendations."""
        try:
            if mood:
                recommendations = self.recommender.recommend_by_mood(mood, count=5)
                print(f"\n{Colors.BOLD}Recommendations for {Colors.YELLOW}{mood}{Colors.END}:")
            else:
                context = self.chat_session.context.copy()
                context.update(self.recommender.get_preference_summary())
                recommendations = self.recommender.get_recommendations(context, count=5)
                print(f"\n{Colors.BOLD}Personalized Recommendations:{Colors.END}")
            
            for i, rec in enumerate(recommendations, 1):
                reason = rec.get("gpt_reason", rec.get("reason", ""))
                print(f"\n  {i}. {Colors.BOLD}{rec['track']}{Colors.END} by {rec['artist']}")
                print(f"     Album:  {rec.get('album', 'Unknown')}")
                print(f"     Why:    {reason}")
            print()
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
    
    def handle_command(self, user_input: str):
        """Handle user command (starts with /)."""
        cmd = user_input.split()[0].lower()
        args = user_input[len(cmd):].strip()
        
        if cmd == "/help":
            self.show_help()
        
        elif cmd == "/current":
            self.show_current_track()
        
        elif cmd == "/pause":
            try:
                state = self.apple_music.play_pause()
                print(f"{Colors.GREEN}✅ {state.capitalize()}{Colors.END}")
            except AppleScriptError as e:
                print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        
        elif cmd == "/skip":
            try:
                result = self.apple_music.skip_track()
                self.chat_session.update_context("current_track", result)
                print(f"{Colors.GREEN}✅ Skipped to: {result['track']} by {result['artist']}{Colors.END}")
            except AppleScriptError as e:
                print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        
        elif cmd == "/play":
            if args:
                try:
                    result = self.apple_music.play_song_by_name(args)
                    self.chat_session.update_context("current_track", result)
                    self.listening_history.add_track(result['track'], result['artist'], result.get('album', 'Unknown'))
                    print(f"{Colors.GREEN}✅ Playing: {result['track']} by {result['artist']}{Colors.END}")
                except AppleScriptError as e:
                    print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
            else:
                print(f"{Colors.YELLOW}Usage: /play <song name> [by <artist>]{Colors.END}")
        
        elif cmd == "/recommend":
            self.get_recommendations()
        
        elif cmd == "/mood":
            if args:
                self.get_recommendations(mood=args)
            else:
                moods = ["chill", "energetic", "relaxing", "focus", "workout"]
                print(f"{Colors.CYAN}Available moods: {', '.join(moods)}{Colors.END}")
                print(f"{Colors.CYAN}Usage: /mood <mood_name>{Colors.END}")
        
        elif cmd == "/rebuild_library":
            print(f"{Colors.CYAN}⏳ Rebuilding library cache...{Colors.END}")
            print(f"{Colors.YELLOW}⚠️  This will take 2-3 minutes for large libraries. Please wait...{Colors.END}")
            try:
                library = self.apple_music.get_all_songs(use_cache=False)
                self.library_cache.save_to_cache(library)
                self.apple_music.library = library  # Update AppleMusic controller with new library
                self.recommender.load_library(library)
                print(f"{Colors.GREEN}✅ Successfully rebuilt cache with {len(library)} songs!{Colors.END}")
                print(f"{Colors.GREEN}   From now on, startup will be instant.{Colors.END}")
            except AppleScriptError as e:
                print(f"{Colors.RED}❌ Library rebuild failed: {e}{Colors.END}")
                print(f"{Colors.CYAN}   💡 Your library might be extremely large. Try again later with more time.{Colors.END}")
        
        elif cmd == "/cache_info":
            info = self.library_cache.get_cache_info()
            print(f"\n{Colors.BOLD}Library Cache Info:{Colors.END}")
            print(f"  Exists:        {Colors.GREEN if info['exists'] else Colors.YELLOW}{'Yes' if info['exists'] else 'No'}{Colors.END}")
            print(f"  Path:          {info['path']}")
            print(f"  Size:          {info['size_bytes']:,} bytes")
            print(f"  Songs:         {info['song_count']}")
            print(f"  Last Modified: {info['last_modified'] or 'Never'}")
            print()
        
        elif cmd == "/history":
            limit = int(args) if args and args.isdigit() else 10
            self.show_history(limit=limit)
        
        elif cmd == "/status":
            self.show_status()
        
        elif cmd == "/quit":
            print(f"{Colors.CYAN}Saving history and exiting...{Colors.END}")
            self.listening_history.save_to_file()
            self.running = False
        
        else:
            print(f"{Colors.YELLOW}Unknown command: {cmd}. Type /help for available commands.{Colors.END}")
    
    def handle_chat(self, user_input: str):
        """Handle natural language chat input."""
        try:
            # Process through chat manager
            processed = self.chat_session.process_user_input(user_input)
            intent = processed["intent"]
            entities = processed["entities"]
            
            # Get GPT response
            history = self.chat_session.get_context_window(num_turns=5)
            context = self.chat_session.context.copy()
            context.update(self.recommender.get_preference_summary())
            context["play_count"] = self.listening_history.get_play_count()
            
            response = self.gpt_assistant.chat(user_input, context, history)
            self.chat_session.add_assistant_response(response)
            
            # Perform actions based on intent
            if intent == UserIntent.PLAY and "song" in entities:
                try:
                    result = self.apple_music.play_song_by_name(
                        entities["song"],
                        entities.get("artist")
                    )
                    self.listening_history.add_track(result['track'], result['artist'], result.get('album', 'Unknown'))
                    print(f"{Colors.GREEN}✅ Now playing: {result['track']} by {result['artist']}{Colors.END}")
                except AppleScriptError as e:
                    print(f"{Colors.YELLOW}❌ Could not play song: {e}{Colors.END}")
            
            elif intent == UserIntent.SKIP:
                try:
                    result = self.apple_music.skip_track()
                    print(f"{Colors.GREEN}✅ Skipped. Now: {result['track']}{Colors.END}")
                except AppleScriptError as e:
                    print(f"{Colors.YELLOW}❌ Could not skip: {e}{Colors.END}")
            
            elif intent == UserIntent.PAUSE:
                try:
                    self.apple_music.play_pause()
                except AppleScriptError as e:
                    print(f"{Colors.YELLOW}❌ Could not pause: {e}{Colors.END}")
            
            elif intent == UserIntent.RECOMMEND:
                mood = entities.get("mood")
                print(f"\n{Colors.BOLD}Recommendations:{Colors.END}")
                if mood:
                    recommendations = self.recommender.recommend_by_mood(mood, count=3)
                else:
                    context = self.chat_session.context.copy()
                    context.update(self.recommender.get_preference_summary())
                    recommendations = self.recommender.get_recommendations(context, count=3)
                
                for rec in recommendations:
                    reason = rec.get("reason", "Personalized for you")
                    print(f"  • {rec['track']} by {rec['artist']} - {reason}")
            
            # Print assistant response
            print(f"\n{Colors.BLUE}🤖 Assistant:{Colors.END}\n{response}\n")
        
        except Exception as e:
            logger.error(f"Chat error: {e}")
            print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
    
    def run(self):
        """Start the interactive CLI."""
        self.print_header()
        
        while self.running:
            try:
                user_input = input(f"{Colors.CYAN}You: {Colors.END}").strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    self.handle_command(user_input)
                else:
                    self.handle_chat(user_input)
            
            except KeyboardInterrupt:
                print(f"\n{Colors.CYAN}Goodbye! 👋{Colors.END}")
                self.listening_history.save_to_file()
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"{Colors.RED}❌ Error: {e}{Colors.END}")


def main():
    """Main entry point."""
    try:
        cli = AppleMusicCLI()
        cli.run()
    except ValueError as e:
        print(f"{Colors.RED}❌ {e}{Colors.END}")
        print(f"{Colors.YELLOW}Please check your .env file has GITHUB_TOKEN set.{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Fatal error: {e}{Colors.END}")


if __name__ == "__main__":
    main()
