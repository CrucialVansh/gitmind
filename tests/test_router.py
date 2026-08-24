"""
Tests for gitmind/router.py

Run with:  pytest tests/test_router.py -v
"""

import pytest
from gitmind.router import route
from gitmind.models import QueryIntent


# ── Rationale queries ──────────────────────────────────────────────────────────

def test_route_why_did():
    assert route("why did we switch from REST to gRPC?") == QueryIntent.RATIONALE


def test_route_why_does():
    assert route("why does fetchUserWithRetry only retry on 503?") == QueryIntent.RATIONALE


def test_route_what_was_the_reason():
    assert route("what was the reason for switching to JWT?") == QueryIntent.RATIONALE


def test_route_how_did_we_decide():
    assert route("how did we decide on the cache TTL?") == QueryIntent.RATIONALE


def test_route_why_not():
    assert route("why not use Redis instead of Memcached?") == QueryIntent.RATIONALE


# ── Structural queries ────────────────────────────────────────────────────────

def test_route_where_is():
    assert route("where is the retry logic?") == QueryIntent.STRUCTURAL


def test_route_which_file():
    assert route("which file handles authentication?") == QueryIntent.STRUCTURAL


def test_route_what_calls():
    assert route("what calls the processOrder function?") == QueryIntent.STRUCTURAL


def test_route_find_function():
    assert route("find the rate limiting function") == QueryIntent.STRUCTURAL


# ── Episode queries ───────────────────────────────────────────────────────────

def test_route_what_did():
    assert route("what did we discuss about error handling?") == QueryIntent.EPISODE


def test_route_tell_me_about():
    assert route("tell me about the migration plan") == QueryIntent.EPISODE


def test_route_explain():
    assert route("explain the caching strategy") == QueryIntent.EPISODE


# ── Default / fallback ────────────────────────────────────────────────────────

def test_route_unknown_defaults_to_episode():
    """Queries that don't match any pattern should default to EPISODE."""
    assert route("rate limiting") == QueryIntent.EPISODE
    assert route("authentication flow") == QueryIntent.EPISODE


def test_route_case_insensitive():
    """Routing should be case-insensitive."""
    assert route("WHY DID WE CHANGE THE API?") == QueryIntent.RATIONALE
    assert route("Where Is The Config File?") == QueryIntent.STRUCTURAL
