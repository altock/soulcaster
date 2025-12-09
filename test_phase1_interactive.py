#!/usr/bin/env python3
"""
Interactive test script for Phase 1 - feedback:unclustered functionality
Run this to manually test the store functions
"""

import sys
import os
from uuid import uuid4
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.models import FeedbackItem, Project
from backend.store import (
    add_feedback_item,
    get_all_feedback_items,
    get_unclustered_feedback,
    remove_from_unclustered,
    clear_feedback_items,
    create_project,
)

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def main():
    print("🧪 Phase 1: Interactive Test Script")
    print("Testing feedback:unclustered functionality\n")
    
    project_id = uuid4()
    project = Project(
        id=project_id,
        user_id=uuid4(),
        name="Interactive Test Project",
        created_at=datetime.now(),
    )
    create_project(project)
    print(f"📦 Using project {project_id}")
    
    # Clear existing data
    print("🧹 Clearing existing feedback...")
    clear_feedback_items()
    print("✅ Cleared\n")
    
    # Test 1: Add feedback items
    print_section("Test 1: Adding Feedback Items")
    
    items = [
        FeedbackItem(
            id=uuid4(),
            project_id=project_id,
            source="reddit",
            external_id="t3_test1",
            title="Bug in login",
            body="Can't login on mobile",
            metadata={"subreddit": "bugs"},
            created_at=datetime.now()
        ),
        FeedbackItem(
            id=uuid4(),
            project_id=project_id,
            source="sentry",
            external_id="sentry_001",
            title="ValueError in process_payment",
            body="ValueError: Invalid amount\nTraceback...",
            metadata={"level": "error"},
            created_at=datetime.now()
        ),
        FeedbackItem(
            id=uuid4(),
            project_id=project_id,
            source="manual",
            title="Dashboard is slow",
            body="The dashboard takes 5+ seconds to load",
            metadata={},
            created_at=datetime.now()
        ),
    ]
    
    for item in items:
        add_feedback_item(item)
        print(f"✅ Added {item.source} feedback: {item.id}")
    
    # Test 2: Get all feedback
    print_section("Test 2: Get All Feedback Items")
    all_items = get_all_feedback_items()
    print(f"Total feedback items: {len(all_items)}")
    for item in all_items:
        print(f"  - {item.source}: {item.title[:50]}")
    
    # Test 3: Get unclustered feedback (KEY TEST!)
    print_section("Test 3: Get Unclustered Feedback (KEY TEST)")
    unclustered = get_unclustered_feedback(project_id)
    print(f"✅ Unclustered items: {len(unclustered)}")
    print(f"Expected: {len(items)}")
    
    if len(unclustered) == len(items):
        print("✅ PASS: All items are in unclustered set!")
    else:
        print("❌ FAIL: Mismatch in unclustered count")
        return 1
    
    for item in unclustered:
        print(f"  - {item.source}: {item.title[:50]}")
    
    # Test 4: Remove from unclustered
    print_section("Test 4: Remove Item from Unclustered")
    item_to_remove = unclustered[0]
    print(f"Removing: {item_to_remove.source} - {item_to_remove.title[:50]}")
    
    remove_from_unclustered(item_to_remove.id, project_id)
    print("✅ Removed")
    
    # Test 5: Verify removal
    print_section("Test 5: Verify Removal")
    unclustered_after = get_unclustered_feedback(project_id)
    print(f"Unclustered items after removal: {len(unclustered_after)}")
    print(f"Expected: {len(items) - 1}")
    
    if len(unclustered_after) == len(items) - 1:
        print("✅ PASS: Item successfully removed from unclustered!")
    else:
        print("❌ FAIL: Removal didn't work correctly")
        return 1
    
    # Verify removed item is NOT in unclustered
    removed_ids = [str(item.id) for item in unclustered_after]
    if str(item_to_remove.id) not in removed_ids:
        print(f"✅ PASS: Removed item {item_to_remove.id} not in unclustered set")
    else:
        print(f"❌ FAIL: Removed item {item_to_remove.id} still in unclustered set")
        return 1
    
    # Test 6: Verify item still exists in all_items
    print_section("Test 6: Verify Item Still Exists (Not Deleted)")
    all_after_removal = get_all_feedback_items()
    all_ids = [str(item.id) for item in all_after_removal]
    
    if str(item_to_remove.id) in all_ids:
        print("✅ PASS: Item still exists in storage (only removed from unclustered)")
    else:
        print("❌ FAIL: Item was deleted from storage!")
        return 1
    
    # Summary
    print_section("🎉 Test Summary")
    print("✅ All Phase 1 tests PASSED!")
    print("\nWhat we verified:")
    print("  ✓ Feedback items are added to unclustered set")
    print("  ✓ get_unclustered_feedback() returns correct items")
    print("  ✓ remove_from_unclustered() removes items from set")
    print("  ✓ Removed items still exist in storage")
    print("  ✓ All sources (reddit, sentry, manual) work correctly")
    print("\n✨ Phase 1 ingestion moat is working!")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

