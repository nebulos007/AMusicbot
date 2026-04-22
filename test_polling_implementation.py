#!/usr/bin/env python3
"""
Quick verification test for polling thread implementation.

Tests:
1. Imports work correctly
2. ListeningHistory new methods exist and work
3. TrackPoller class initializes correctly
4. Skip categorization logic works as expected
"""

import sys
from datetime import datetime, timedelta

print("=" * 60)
print("Testing Background Polling Implementation")
print("=" * 60)

# Test 1: Import all modules
print("\n[Test 1] Importing modules...")
try:
    from listening_history import ListeningHistory
    from apple_music import AppleMusicController, TrackPoller
    print("✓ All imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: ListeningHistory new methods
print("\n[Test 2] Testing ListeningHistory new methods...")
try:
    history = ListeningHistory("test_history.json")
    
    # Test add_track with skip_type
    event = history.add_track(
        track="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=240,
        skip_type="immediate_skip",
        percentage_played=15.5,
        started_at=datetime.now() - timedelta(seconds=37),
        ended_at=datetime.now()
    )
    assert event["skip_type"] == "immediate_skip", "skip_type not set correctly"
    assert event["percentage_played"] == 15.5, "percentage_played not rounded correctly"
    print("✓ add_track with skip_type works")
    
    # Test add_complete_listen
    event2 = history.add_complete_listen(
        track="Complete Song",
        artist="Test Artist 2",
        album="Test Album 2",
        duration=200,
        started_at=datetime.now() - timedelta(seconds=200),
        ended_at=datetime.now()
    )
    assert event2["skip_type"] == "complete_listen", "complete_listen not set"
    assert event2["percentage_played"] == 100.0, "complete_listen should be 100%"
    print("✓ add_complete_listen works")
    
    # Test get_skip_signals
    signals = history.get_skip_signals()
    assert "positive" in signals, "signals missing 'positive'"
    assert "neutral" in signals, "signals missing 'neutral'"
    assert "negative" in signals, "signals missing 'negative'"
    assert len(signals["positive"]) == 1, "should have 1 positive (complete_listen)"
    assert len(signals["negative"]) == 1, "should have 1 negative (immediate_skip)"
    print("✓ get_skip_signals works")
    
    print("✓ ListeningHistory methods all working")
except Exception as e:
    print(f"✗ ListeningHistory test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: TrackPoller initialization (without polling)
print("\n[Test 3] Testing TrackPoller initialization...")
try:
    # Mock AppleMusicController
    class MockController:
        def get_current_track(self):
            return None
    
    mock_controller = MockController()
    history2 = ListeningHistory("test_history2.json")
    
    poller = TrackPoller(mock_controller, history2)
    assert poller.running == False, "Poller should not be running initially"
    assert poller.poll_interval == 5, "Default poll interval should be 5s"
    print("✓ TrackPoller initializes correctly")
except Exception as e:
    print(f"✗ TrackPoller test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Skip categorization logic
print("\n[Test 4] Testing skip categorization logic...")
try:
    poller2 = TrackPoller(mock_controller, history2)
    
    # Test immediate skip (5%)
    history2.history = []  # Reset
    poller2.track_started_at = datetime.now() - timedelta(seconds=12)
    event_immed = poller2.log_skip({"track": "Song", "artist": "Artist", "album": "Album", "duration": 240})
    assert event_immed["skip_type"] == "immediate_skip", "5% should be immediate_skip"
    print(f"✓ 5% elapsed → immediate_skip")
    
    # Test late skip (85%)
    history2.history = []  # Reset
    poller2.track_started_at = datetime.now() - timedelta(seconds=204)
    event_late = poller2.log_skip({"track": "Song 2", "artist": "Artist 2", "album": "Album 2", "duration": 240})
    assert event_late["skip_type"] == "late_skip", "85% should be late_skip"
    print(f"✓ 85% elapsed → late_skip")
    
    # Test partial skip (50%)
    history2.history = []  # Reset
    poller2.track_started_at = datetime.now() - timedelta(seconds=120)
    event_partial = poller2.log_skip({"track": "Song 3", "artist": "Artist 3", "album": "Album 3", "duration": 240})
    assert event_partial["skip_type"] == "partial_skip", "50% should be partial_skip"
    print(f"✓ 50% elapsed → partial_skip")
    
    print("✓ Skip categorization logic all working")
except Exception as e:
    print(f"✗ Skip categorization test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Cleanup
print("\n[Test 5] Cleanup...")
try:
    import os
    os.remove("test_history.json")
    os.remove("test_history2.json")
    print("✓ Test files cleaned up")
except Exception as e:
    print(f"⚠ Cleanup warning: {e}")

print("\n" + "=" * 60)
print("All tests passed! ✓")
print("=" * 60)
print("\nImplementation Summary:")
print("1. ListeningHistory now tracks skips with elapsed time % and categorization")
print("2. TrackPoller background thread monitors track changes automatically")
print("3. Skip types: immediate_skip (<20%), partial_skip (20-80%), late_skip (>80%)")
print("4. Complete listens (100%) logged when track ends naturally")
print("5. All events include timing metadata for preference analysis")
print("\nReady for manual testing with CLI!")
