"""
Circuit Breaker pattern for external service calls.

Prevents cascading failures by temporarily blocking calls to failing services.

USAGE:
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60)
    
    if breaker.is_available():
        try:
            result = call_external_service()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
            raise
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""
    failures: int = 0
    last_failure: datetime | None = None
    is_open: bool = False
    successes_since_half_open: int = 0


class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests blocked
    - HALF-OPEN: Testing recovery, limited requests allowed
    
    Transitions:
    - CLOSED -> OPEN: When failure_threshold reached
    - OPEN -> HALF-OPEN: After recovery_timeout
    - HALF-OPEN -> CLOSED: After success_threshold successes
    - HALF-OPEN -> OPEN: On any failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout_seconds: Time before attempting recovery
            success_threshold: Successes needed to close circuit from half-open
        """
        self._state = CircuitBreakerState()
        self._lock = Lock()
        self._failure_threshold = failure_threshold
        self._recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self._success_threshold = success_threshold

    def is_available(self) -> bool:
        """
        Check if circuit is available for requests.
        
        Returns:
            True if circuit is closed or half-open (testing recovery)
        """
        with self._lock:
            if not self._state.is_open:
                return True
            
            # Check if recovery timeout has passed (move to half-open)
            if self._state.last_failure:
                elapsed = datetime.now(timezone.utc) - self._state.last_failure
                if elapsed > self._recovery_timeout:
                    # Half-open state - allow request
                    return True
            
            return False

    def record_failure(self) -> None:
        """
        Record a failure. Opens circuit if threshold reached.
        """
        with self._lock:
            self._state.failures += 1
            self._state.last_failure = datetime.now(timezone.utc)
            self._state.successes_since_half_open = 0
            
            if self._state.failures >= self._failure_threshold:
                self._state.is_open = True

    def record_success(self) -> None:
        """
        Record a success. May close circuit if in half-open state.
        """
        with self._lock:
            if self._state.is_open:
                # In half-open state
                self._state.successes_since_half_open += 1
                if self._state.successes_since_half_open >= self._success_threshold:
                    # Enough successes - close circuit
                    self._state.is_open = False
                    self._state.failures = 0
                    self._state.successes_since_half_open = 0
            else:
                # Already closed - just reset failure count
                self._state.failures = 0

    def reset(self) -> None:
        """
        Manually reset the circuit breaker to closed state.
        """
        with self._lock:
            self._state = CircuitBreakerState()

    @property
    def state(self) -> str:
        """
        Get current state as string.
        
        Returns:
            "CLOSED", "OPEN", or "HALF-OPEN"
        """
        with self._lock:
            if not self._state.is_open:
                return "CLOSED"
            
            if self._state.last_failure:
                elapsed = datetime.now(timezone.utc) - self._state.last_failure
                if elapsed > self._recovery_timeout:
                    return "HALF-OPEN"
            
            return "OPEN"

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._state.failures

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.
        
        Returns:
            Dict with state, failures, etc.
        """
        with self._lock:
            return {
                "state": self.state,
                "failures": self._state.failures,
                "is_open": self._state.is_open,
                "last_failure": self._state.last_failure.isoformat() if self._state.last_failure else None,
                "threshold": self._failure_threshold,
                "recovery_timeout_seconds": self._recovery_timeout.total_seconds(),
            }
