"""
User quota limits for free tier.

This module defines quota limits for free-tier users and provides
enforcement functions. When implementing paid tiers, replace hardcoded
constants with tier-based lookups from database.
"""

from store import count_feedback_items_for_user, count_successful_jobs_for_user

# Free tier limits
FREE_TIER_MAX_ISSUES = 1500
FREE_TIER_MAX_JOBS = 20

# TODO: When implementing paid plans, add tier-based limit lookup:
# def get_limits_for_user(user_id: str) -> tuple[int, int]:
#     user_tier = get_user_tier(user_id)
#     return TIER_LIMITS[user_tier]


def check_feedback_item_limit(
    user_id: str,
    count: int = 1,
) -> tuple[bool, int]:
    """
    Check if adding feedback items would exceed user's limit.

    Args:
        user_id: User ID to check quota for
        count: Number of items to add (default 1)

    Returns:
        Tuple of (can_add: bool, current_count: int)
    """
    current_count = count_feedback_items_for_user(user_id)
    can_add = (current_count + count) <= FREE_TIER_MAX_ISSUES
    return can_add, current_count


def check_coding_job_limit(user_id: str) -> tuple[bool, int]:
    """
    Check if creating a coding job would exceed user's limit.

    Args:
        user_id: User ID to check quota for

    Returns:
        Tuple of (can_create: bool, current_count: int)
    """
    current_count = count_successful_jobs_for_user(user_id)
    can_create = current_count < FREE_TIER_MAX_JOBS
    return can_create, current_count
