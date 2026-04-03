# 🎵 Apple Music AI Chatbot - MCP Server

A sophisticated music discovery and playback control system that provides intelligent recommendations for exploring new artists. Combines AppleScript integration, GPT-4o powered discovery with song-specific Apple Music links, and listening history tracking for a seamless music exploration experience.

## 🎯 Features

### Music Discovery & Recommendations
- **GPT-Powered Discovery** - Get personalized recommendations for NEW artists you haven't discovered yet (not just songs from your library)
- **Song-Specific Links** - Each recommended song comes with a clickable Apple Music link for instant exploration
- **Mood-Based Suggestions** - "Give me something energetic" → GPT analyzes your taste and suggests new artists with specific songs
- **Natural Language Requests** - Ask for music in any way you want, like "Something upbeat for a workout" or "Chill artists like Aloe Blacc"
- **Smart Fallback Matching** - When GPT discovery isn't available, uses content-based filtering to suggest similar music from your library

### Playback Control
- **Play/Pause** - Control playback seamlessly
- **Skip Track** - Move to the next song
- **Current Track Info** - Display what's playing with artist and album
- **Player State** - Query current playback status

### Learning & Personalization
- **Listening History** - Automatically tracks plays and skips over time
- **Preference Building** - System learns from your choices (songs you play vs skip)
- **Context Awareness** - Remembers your mood, current track, and recent preferences
- **Continuous Improvement** - Recommendations improve the more you use it

### Intelligent Chat
- **Multi-turn Conversations** - Maintains context across multiple interactions
- **Intent Detection** - Understands if you want to play, skip, get recommendations, or chat
- **Natural Explanations** - GPT explains why it recommended each artist
- **Conversational Discovery** - Chat naturally about music to get suggestions

## 🏗️ Architecture

### How It Works: Discovery Flow

```
User: "Give me upbeat artists"
         ↓
    CLI Input
         ↓
  Chat Manager (Intent Detection)
         ↓
    Recommender Engine
         ↓
  📊 Library Summary ──→ GPT-4o Analysis
  (Top artists, genres)
         ↓
  GPT Returns: "Artist | Why | Songs: Song1, Song2, Song3"
         ↓
  Parse & Generate Apple Music Links for Each Song
         ↓
  Display with Individual Links:
  🎵 Artist Name
     Recommended because: [explanation]
     Suggested songs:
     • Song 1 https://music.apple.com/search?term=Song+1+Artist
     • Song 2 https://music.apple.com/search?term=Song+2+Artist  
     • Song 3 https://music.apple.com/search?term=Song+3+Artist
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CLI Interface (cli.py)                │
│              (Interactive Terminal Chat)                │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               MCP Server (mcp_server.py)                │
│         (Orchestrator & Tool Exposure Layer)            │
└────┬────────┬────────┬────────┬────────┬───────────────┘
     │        │        │        │        │
     ▼        ▼        ▼        ▼        ▼
┌────────┐┌──────────┐┌──────────────┐┌──────┐┌──────────┐
│ Apple  ││   Chat   ││ Recommender  ││ Hist.││    GPT   │
│ Music  ││ Manager  ││   Engine     ││ Mgmt ││  4o via  │
│(AppleS)││ (Intent) ││(GPT-powered  ││      ││ GitHub   │
│        ││          ││ + Content     ││      ││ endpoint │
└────────┘└──────────┘└──────────────┘└──────┘└──────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `apple_music.py` | AppleScript wrapper + Apple Music URL generation |
| `chat_manager.py` | Conversation state & intent detection |
| `recommender.py` | GPT-powered discovery + content-based fallback |
| `listening_history.py` | Persistent play/skip tracking |
| `utils/gpt_integration.py` | GitHub inference endpoint integration (GPT-4o) |
| `mcp_server.py` | MCP server with exposed tools/resources |
| `cli.py` | Interactive command-line interface |

### Key Integration Points

1. **Recommender + GPT**: Analyzes user library to inform discovery
2. **Recommender + Apple Music**: Gets library summary and generates search URLs
3. **Chat Manager + Recommender**: Routes natural language to discovery
4. **CLI + Apple Music**: Displays individual song links for exploration

## 🚀 Getting Started

### Prerequisites

- **macOS** (Apple Music app required)
- **Python 3.10+**
- **GitHub token** with access to GPT-4o inference API (models.github.ai)
- Apple Music subscription (optional for demo with mock data)

### Installation

1. **Navigate to project directory:**
   ```bash
   cd AMusicbot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   # Create or verify .env file with your GitHub token
   echo "GITHUB_TOKEN=your-github-token-here" > .env
   ```
   
   Your GitHub token needs access to the GitHub models API. Get one at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo` scope.

### Running the Chatbot

**Start the interactive CLI** (recommended for exploring music):
```bash
python cli.py
```

**Note on MCP Server:**
The `mcp_server.py` is a background service for IDE integration and is not meant for interactive use. The CLI (`cli.py`) is your interface to the music discovery bot.

## 💬 Usage Examples

### Getting Recommendations (Discovery Mode)

The system analyzes your music taste and suggests **NEW artists you haven't discovered** with specific songs to check out:

```
You: Give me some upbeat artists

🤖 ✨ NEW ARTISTS TO DISCOVER:

1. Twenty One Pilots
   Great for mixing electronic and alternative rock energy into your taste.
   🎵 Suggested songs:
   • Stressed Out
     https://music.apple.com/search?term=Stressed%20Out%20Twenty%20One%20Pilots
   • Heathens
     https://music.apple.com/search?term=Heathens%20Twenty%20One%20Pilots
   • Ride
     https://music.apple.com/search?term=Ride%20Twenty%20One%20Pilots

2. Hyperpop Artist Name
   [Similar format with 3 songs and direct Apple Music links...]

3. Electronic Artist Name
   [Similar format with 3 songs and direct Apple Music links...]
```

Click any Apple Music link to instantly listen and explore the song!

### CLI Commands

```bash
# Start interactive chat
python cli.py

# In the chat, you can:
# - Ask for music by mood: "Give me something chill"
# - Request by genre: "I want upbeat indie artists"
# - Ask naturally: "Play something that sounds like Leon Bridges"
# - Get recommendations: "/recommend"
# - Check current track: "/current"
# - Skip to next: "/skip"
# - View history: "/history"
# - Exit: "/quit"
```

### Natural Language Discovery

```
You: Give me some great indie artists to explore

🤖 Analyzing your music taste (4,800+ songs, top genres: indie, alternative, pop)...

✨ NEW ARTISTS TO DISCOVER:

1. The National
   Your taste includes bands like Alt-J and Interpol; The National brings
   intelligent rock with introspective lyrics you'll appreciate.
   
   🎵 Suggested songs:
   • Fake Empire
     https://music.apple.com/search?term=Fake%20Empire%20The%20National
   • Bloodhail
     https://music.apple.com/search?term=Bloodhail%20The%20National
   • About Today
     https://music.apple.com/search?term=About%20Today%20The%20National

[Similar discoveries for more artists...]

You: I love The National! Give me similar artists

🤖 Based on The National's sophisticated instrumentation and introspective style,
here are complementary artists:

✨ NEW ARTISTS TO DISCOVER:

1. Interpol
   [Recommendations with song links...]
```

## 📊 How Music Discovery Works

### How GPT-Powered Discovery Works

The system uses GPT-4o to analyze your music taste and suggest NEW artists:

1. **Library Analysis** - Extracts your top 5 artists and top 3 genres
2. **Preference Summary** - Builds a profile: "You love indie rock with elements of folk, artists like [Top Artists]"
3. **GPT Discovery** - Sends to GPT-4o: "Based on this taste profile, suggest NEW artists they haven't discovered with specific recommended songs"
4. **Smart Parsing** - Extracts artist recommendations and suggested songs from GPT response
5. **Link Generation** - Creates individual Apple Music search links for each suggested song
6. **Display** - Shows recommendations with explanations and clickable links

**Example Flow:**
```
Your Library → Extract: {indie, alternative, pop} + Top Artists
               ↓
          Send to GPT-4o: "User likes [Artists]. Suggest NEW similar artists"
               ↓
          GPT Returns: "Artist1 | Why | Songs: Song1, Song2, Song3"
               ↓
          Parse & Generate URLs
               ↓
          Display with links to each song
```

### What Happens if GPT Discovery Isn't Available

The system falls back to **content-based similarity filtering**:
- Analyzes songs in your library for genre and style similarity
- Recommends songs from artists in your collection that match your taste
- Still useful but limited to artists you already know

### How the System Learns

Every song you play or skip is recorded:
- **Plays** = positive signal (you liked it)
- **Skips** = negative signal (it wasn't what you wanted)
- This data improves recommendation accuracy over time

Over many sessions:
- System learns your exact mood preferences
- Better able to predict what you'll want to hear
- Recommendations become increasingly personalized

## 🔧 Technical Details

### Apple Music Integration

**URL Generation for Song Discovery:**
```python
apple_music.get_apple_music_search_url(song_name="River", artist="Leon Bridges")
# Returns: https://music.apple.com/search?term=River+Leon+Bridges
```

This creates clickable links that users can visit to instantly find and play songs in the Apple Music app.

**AppleScript Control:**
```python
apple_music.play_pause()      # Toggle playback
apple_music.skip_track()      # Go to next song
apple_music.get_current_track()  # Get now playing info
apple_music.get_all_songs()   # Load full library (cached)
```

**AppleScript Limitations:**
- Single-threaded (operations are queued)
- Large library queries can be slow (mitigated with caching)
- macOS only (requires Music app)
- Limited to what AppleScript exposes

**URL Encoding:**
Songs with special characters are safely encoded:
- `"Don't Stop Me Now"` → `Don%27t%20Stop%20Me%20Now`
- Spaces become `%20` or `+`
- Special chars safely escaped via `urllib.parse.quote()`

### GPT-4o Integration via GitHub

Uses ChatOpenAI with GitHub's model inference endpoint:

```python
ChatOpenAI(
    model="openai/gpt-4o",
    base_url="https://models.github.ai/inference",
    api_key=github_token  # From .env
)
```

**Why GitHub's Inference Endpoint:**
- ✅ Direct access to GPT-4o without separate OpenAI account
- ✅ Uses your existing GitHub token
- ✅ Streaming support for long responses
- ✅ No additional costs (included with GitHub)

**Prompt Engineering:**
The discovery prompt explicitly formats GPT responses:
```
Format EXACTLY like this:
Artist Name | Why they're a great fit | Suggested songs: Song1, Song2, Song3
```

This strict format ensures reliable parsing of recommendations.

### Smart Library Caching

For users with large music libraries (2000+ songs), AppleScript queries are slow. The bot implements disk-based caching:

**First Run (Cold Start):**
```
⏳ Building library cache...
⚠️  This may take 2-3 minutes for large libraries. Please wait...
✅ Loaded and cached 4,804 songs
```

**Subsequent Runs (Warm Start):**
```
✅ Loaded 4,804 songs from cache (instant)
```

The cache loads in under 1 second from `library_cache.json`.

**Cache Details:**
- Stored as JSON (human-readable)
- ~10-20 MB for large libraries (4000+ songs)
- Automatically created after first library load
- Survives across sessions and CLI restarts
- Rebuild with `/rebuild_library` if music library changes

### Persistent Listening History

Plays and skips are recorded to `listening_history.json`:

```json
{
  "plays": [
    {
      "type": "play",
      "track": "River",
      "artist": "Leon Bridges",
      "album": "Coming Home",
      "duration": 245,
      "timestamp": "2025-04-02T10:30:45"
    }
  ],
  "last_updated": "2025-04-02T10:35:12",
  "total_plays": 42
}
```

This data persists across sessions, enabling better recommendations over time.

## 🧪 Testing

### Manual Testing - The Discovery Workflow

Test the complete music discovery experience:

```bash
# Start the CLI
python cli.py

# Test 1: Basic discovery
You: "Give me some great artists to explore"
🤖 Should show 5+ new artists with songs and Apple Music links

# Test 2: Mood-based discovery  
You: "I want upbeat energetic artists"
🤖 Should suggest artists in high-energy genres

# Test 3: Style-based discovery
You: "Artists like Leon Bridges"
🤖 Should suggest soulful R&B and similar genres

# Test 4: Click the links!
- Each song link should work: https://music.apple.com/search?term=Song+Artist
- Click and verify Apple Music opens with search results
```

### Testing Song Link Generation

The recommender should generate valid Apple Music URLs:
- ✅ `"River"` → `https://music.apple.com/search?term=River+Leon+Bridges`
- ✅ `"Don't Stop Me Now"` → `https://music.apple.com/search?term=Don%27t%20Stop%20Me%20Now+Queen`
- ✅ Special characters properly URL-encoded
- ✅ Each song has its own unique link

### CLI Display Format

Recommendations should display as:
```
✨ NEW ARTISTS TO DISCOVER:

1. Artist Name
   Why they fit your taste: [GPT explanation]
   🎵 Suggested songs:
   • Song 1
     https://music.apple.com/search?term=Song%201+Artist
   • Song 2  
     https://music.apple.com/search?term=Song%202+Artist
   • Song 3
     https://music.apple.com/search?term=Song%203+Artist
```

## 📁 Project Structure

```
AMusicbot/
├── requirements.txt              # Dependencies
├── .env                         # GitHub token (gitignored)
├── .gitignore                   # Git exclusions
├── README.md                    # This file
│
├── apple_music.py               # AppleScript wrapper (AppleMusicController)
├── chat_manager.py              # Conversation management (MusicChatSession)
├── recommender.py               # Recommendation engine (MusicRecommender)
├── listening_history.py         # History persistence (ListeningHistory)
├── library_cache.py             # Library caching (LibraryCache)
├── mcp_server.py                # MCP server with tools & resources
├── cli.py                       # Interactive CLI interface
│
├── utils/
│   ├── __init__.py
│   └── gpt_integration.py        # GPT-4o via GitHub inference (GPTMusicAssistant)
│
├── tests/
│   ├── test_recommender.py
│   ├── test_apple_music.py
│   ├── test_chat_manager.py
│   ├── test_listening_history.py
│   └── test_library_cache.py
│
├── listening_history.json       # Persistent play history (auto-created)
└── library_cache.json           # Cached music library (auto-created)
```

## 🔮 Future Improvements

### Discovery Enhancements
1. **Playlist Generation** - Create Spotify/Apple playlists from GPT recommendations
2. **Genre Deep Dives** - "Show me jazz artists" → targeted discovery by explicit genre
3. **Time-Based Recommendations** - Morning upbeat vs evening chill artists
4. **Skip-Reason Tracking** - "Why did you skip?" → learn more precisely
5. **Discovery Chains** - "Artists similar to the artists I just discovered"

### Playback & Control
1. **Volume Control** - Adjust via AppleScript
2. **Shuffle/Repeat** - Toggle modes
3. **Queue Management** - View and modify up next
4. **Lyrics Display** - Show lyrics from selected song

### Music Intelligence
1. **Artist Bio Generation** - GPT explains why an artist fits your taste
2. **Mood Progression** - Track your mood changes over time
3. **Discovery Statistics** - "You've discovered 247 new artists this month"
4. **Export Recommendations** - Share found artists with friends

### User Experience
1. **Web Interface** - Browser-based discovery (vs terminal)
2. **Conversation Persistence** - Save discovery conversations
3. **Saved Recommendations** - Bookmark artists to check out later
4. **Collaborative Discovery** - Share taste profile with friends

### Advanced Features
1. **Multi-User Support** - Different profiles with separate histories
2. **Spotify Integration** - Read library from other services
3. **Analytics Dashboard** - Statistics about your music taste
4. **LLM Fine-tuning** - Train custom model on your full library

## 📝 License

MIT License - See LICENSE file for details.
