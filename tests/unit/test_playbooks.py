import pytest
from src.workflows.playbooks import find_matching_playbook

def test_find_matching_playbook_performance():
    # Vague performance/slowness reports must map to Performance Investigation
    assert find_matching_playbook("my program is slow") is not None
    assert find_matching_playbook("my program is slow").name == "Performance Investigation"
    
    assert find_matching_playbook("API is timing out") is not None
    assert find_matching_playbook("API is timing out").name == "Performance Investigation"
    
    assert find_matching_playbook("the app is lagging") is not None
    assert find_matching_playbook("the app is lagging").name == "Performance Investigation"

    # Specific database/build slowness must also map to Performance Investigation as per spec
    assert find_matching_playbook("database is slow") is not None
    assert find_matching_playbook("database is slow").name == "Performance Investigation"

    assert find_matching_playbook("build is slow") is not None
    assert find_matching_playbook("build is slow").name == "Performance Investigation"

    assert find_matching_playbook("tests are too slow") is not None
    assert find_matching_playbook("tests are too slow").name == "Performance Investigation"

def test_find_matching_playbook_flaky_tests():
    # Flaky tests (not just slow tests) must map to Flaky Test Investigation
    assert find_matching_playbook("flaky test in login") is not None
    assert find_matching_playbook("flaky test in login").name == "Flaky Test Investigation"
    
    assert find_matching_playbook("test fails sometimes") is not None
    assert find_matching_playbook("test fails sometimes").name == "Flaky Test Investigation"

def test_find_matching_playbook_memory():
    assert find_matching_playbook("memory leak detected in gateway") is not None
    assert find_matching_playbook("memory leak detected in gateway").name == "Memory Leak Investigation"
    
    assert find_matching_playbook("OOM crash") is not None
    assert find_matching_playbook("OOM crash").name == "Memory Leak Investigation"

def test_find_matching_playbook_cpu():
    assert find_matching_playbook("100% CPU usage on server") is not None
    assert find_matching_playbook("100% CPU usage on server").name == "CPU Spike Investigation"

def test_find_matching_playbook_database():
    # Non-slowness DB issues map to Database Investigation
    assert find_matching_playbook("database lock contention") is not None
    assert find_matching_playbook("database lock contention").name == "Database Investigation"

def test_find_matching_playbook_networking():
    assert find_matching_playbook("dns resolution failed") is not None
    assert find_matching_playbook("dns resolution failed").name == "Network & Timeout Investigation"

def test_find_matching_playbook_build():
    # CI configurations and docker compilation map to Build & CI Investigation
    assert find_matching_playbook("ci pipeline caching issue") is not None
    assert find_matching_playbook("ci pipeline caching issue").name == "Build & CI Investigation"

def test_find_matching_playbook_crashes():
    assert find_matching_playbook("NullPointerException in main loop") is not None
    assert find_matching_playbook("NullPointerException in main loop").name == "Crash Investigation"

def test_find_matching_playbook_intermittent():
    assert find_matching_playbook("connection fails occasionally") is not None
    assert find_matching_playbook("connection fails occasionally").name == "Intermittent Failure Investigation"

def test_find_matching_playbook_no_match():
    assert find_matching_playbook("please schedule a planning session") is None
    assert find_matching_playbook("need to build a new feature") is None
