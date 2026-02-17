"""
Tier Limits — per-tier resource and concurrency limits for automations.
"""

from dataclasses import dataclass

from cachibot.services.script_sandbox import AutomationResourceLimits


@dataclass
class TierLimits:
    """Limits for a specific tier."""

    max_automations: int
    min_interval_seconds: int
    max_concurrent_runs: int
    resource_limits: AutomationResourceLimits
    log_retention_days: int
    max_logs_per_item: int
    max_log_lines_per_execution: int


# Tier definitions
_TIER_LIMITS: dict[str, TierLimits] = {
    "free": TierLimits(
        max_automations=3,
        min_interval_seconds=3600,  # 1 hour
        max_concurrent_runs=1,
        resource_limits=AutomationResourceLimits(
            max_cpu_seconds=30.0,
            max_memory_bytes=128 * 1024 * 1024,
            max_wall_seconds=120.0,
        ),
        log_retention_days=7,
        max_logs_per_item=25,
        max_log_lines_per_execution=50,
    ),
    "starter": TierLimits(
        max_automations=10,
        min_interval_seconds=300,  # 5 minutes
        max_concurrent_runs=2,
        resource_limits=AutomationResourceLimits(
            max_cpu_seconds=60.0,
            max_memory_bytes=256 * 1024 * 1024,
            max_wall_seconds=300.0,
        ),
        log_retention_days=14,
        max_logs_per_item=50,
        max_log_lines_per_execution=200,
    ),
    "pro": TierLimits(
        max_automations=50,
        min_interval_seconds=60,  # 1 minute
        max_concurrent_runs=5,
        resource_limits=AutomationResourceLimits(
            max_cpu_seconds=120.0,
            max_memory_bytes=512 * 1024 * 1024,
            max_wall_seconds=600.0,
        ),
        log_retention_days=30,
        max_logs_per_item=100,
        max_log_lines_per_execution=1000,
    ),
    "enterprise": TierLimits(
        max_automations=200,
        min_interval_seconds=10,  # 10 seconds
        max_concurrent_runs=20,
        resource_limits=AutomationResourceLimits(
            max_cpu_seconds=300.0,
            max_memory_bytes=1024 * 1024 * 1024,
            max_wall_seconds=1800.0,
        ),
        log_retention_days=90,
        max_logs_per_item=500,
        max_log_lines_per_execution=100_000,
    ),
}

# Default tier for self-hosted (no tier system)
_DEFAULT_TIER = "pro"


def get_tier_limits(tier: str | None = None) -> TierLimits:
    """Get limits for a specific tier.

    Falls back to the default tier (pro) for self-hosted installations.
    """
    if tier is None:
        tier = _DEFAULT_TIER
    return _TIER_LIMITS.get(tier, _TIER_LIMITS[_DEFAULT_TIER])


def check_automation_count(current_count: int, tier: str | None = None) -> bool:
    """Check if a new automation can be created within tier limits."""
    limits = get_tier_limits(tier)
    return current_count < limits.max_automations


def check_interval(interval_seconds: int, tier: str | None = None) -> bool:
    """Check if a schedule interval meets tier minimum."""
    limits = get_tier_limits(tier)
    return interval_seconds >= limits.min_interval_seconds


def check_concurrency(running_count: int, tier: str | None = None) -> bool:
    """Check if another concurrent run is allowed."""
    limits = get_tier_limits(tier)
    return running_count < limits.max_concurrent_runs
