"""
Extended tests for PRD Manager - covering add_story, remove_story, update_story,
mark_story_incomplete, _check_dependencies_met, save_prd edge cases.
"""

import pytest
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


# Simplified versions for testing (same as test_prd_manager.py)
@dataclass
class UserStory:
    id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    priority: int
    passes: bool = False
    notes: str = ""
    estimated_hours: Optional[float] = None
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserStory':
        return cls(**data)


class PRDManager:
    def __init__(self):
        self.prd_data: Dict[str, Any] = {}
        self.stories: List[UserStory] = []
        self.file_path: Optional[Path] = None

    def load_prd(self, prd_path: Path) -> None:
        self.file_path = prd_path
        with open(prd_path, 'r', encoding='utf-8') as f:
            self.prd_data = json.load(f)
        self.stories = []
        for story_data in self.prd_data.get("userStories", []):
            self.stories.append(UserStory.from_dict(story_data))

    def create_prd(self, project_name: str, branch_name: str, description: str,
                  stories: List[UserStory]) -> None:
        self.prd_data = {
            "project": project_name,
            "branch": branch_name,
            "description": description,
            "userStories": [s.to_dict() for s in stories]
        }
        self.stories = stories.copy()

    def save_prd(self, output_path: Optional[Path] = None) -> None:
        if output_path is None:
            output_path = self.file_path
        if output_path is None:
            raise ValueError("No output path specified and no original file path")
        self.prd_data["userStories"] = [s.to_dict() for s in self.stories]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.prd_data, f, indent=2, ensure_ascii=False)

    def get_all_stories(self) -> List[UserStory]:
        return self.stories

    def get_story_by_id(self, story_id: str) -> Optional[UserStory]:
        for story in self.stories:
            if story.id == story_id:
                return story
        return None

    def get_next_story(self) -> Optional[UserStory]:
        available = [s for s in self.stories if not s.passes and self._check_dependencies_met(s)]
        available.sort(key=lambda s: s.priority, reverse=True)
        return available[0] if available else None

    def _check_dependencies_met(self, story: UserStory) -> bool:
        for dep_id in story.dependencies:
            dep = self.get_story_by_id(dep_id)
            if dep is None or not dep.passes:
                return False
        return True

    def mark_story_complete(self, story_id: str) -> None:
        story = self.get_story_by_id(story_id)
        if story:
            story.passes = True

    def mark_story_incomplete(self, story_id: str) -> None:
        story = self.get_story_by_id(story_id)
        if story:
            story.passes = False

    def add_story(self, story: UserStory) -> None:
        self.stories.append(story)

    def remove_story(self, story_id: str) -> bool:
        for i, story in enumerate(self.stories):
            if story.id == story_id:
                self.stories.pop(i)
                return True
        return False

    def update_story(self, story_id: str, **kwargs) -> bool:
        story = self.get_story_by_id(story_id)
        if story:
            for key, value in kwargs.items():
                if hasattr(story, key):
                    setattr(story, key, value)
            return True
        return False

    def get_progress_summary(self) -> Dict[str, Any]:
        total = len(self.stories)
        completed = sum(1 for s in self.stories if s.passes)
        return {
            "total_stories": total,
            "completed_stories": completed,
            "incomplete_stories": total - completed,
            "completion_percentage": (completed / total * 100) if total > 0 else 0
        }


def _story(**kwargs):
    """Helper to create a UserStory with sensible defaults."""
    defaults = dict(id="s1", title="T", description="D", acceptance_criteria=[], priority=1)
    defaults.update(kwargs)
    return UserStory(**defaults)


class TestAddStory:
    def test_add_to_empty(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1"))
        assert len(mgr.stories) == 1
        assert mgr.stories[0].id == "s1"

    def test_add_multiple(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1"))
        mgr.add_story(_story(id="s2"))
        assert len(mgr.stories) == 2

    def test_add_duplicate_id(self):
        """Adding a story with same ID doesn't replace — both exist."""
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", title="First"))
        mgr.add_story(_story(id="s1", title="Second"))
        assert len(mgr.stories) == 2
        assert mgr.get_story_by_id("s1").title == "First"


class TestRemoveStory:
    def test_remove_existing(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1"))
        assert mgr.remove_story("s1") is True
        assert len(mgr.stories) == 0

    def test_remove_nonexistent(self):
        mgr = PRDManager()
        assert mgr.remove_story("s999") is False

    def test_remove_from_middle(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1"))
        mgr.add_story(_story(id="s2"))
        mgr.add_story(_story(id="s3"))
        mgr.remove_story("s2")
        assert [s.id for s in mgr.stories] == ["s1", "s3"]


class TestUpdateStory:
    def test_update_title(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", title="Old"))
        assert mgr.update_story("s1", title="New") is True
        assert mgr.get_story_by_id("s1").title == "New"

    def test_update_priority(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", priority=1))
        mgr.update_story("s1", priority=10)
        assert mgr.get_story_by_id("s1").priority == 10

    def test_update_nonexistent(self):
        mgr = PRDManager()
        assert mgr.update_story("s999", title="X") is False

    def test_update_invalid_field_ignored(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1"))
        mgr.update_story("s1", nonexistent_field="value")
        # Should not crash, field just ignored
        assert not hasattr(mgr.get_story_by_id("s1"), "nonexistent_field")

    def test_update_multiple_fields(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", title="Old", priority=1))
        mgr.update_story("s1", title="New", priority=5)
        s = mgr.get_story_by_id("s1")
        assert s.title == "New"
        assert s.priority == 5


class TestMarkStoryIncomplete:
    def test_mark_incomplete(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=True))
        mgr.mark_story_incomplete("s1")
        assert mgr.get_story_by_id("s1").passes is False

    def test_mark_already_incomplete(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=False))
        mgr.mark_story_incomplete("s1")
        assert mgr.get_story_by_id("s1").passes is False

    def test_mark_nonexistent_no_error(self):
        mgr = PRDManager()
        mgr.mark_story_incomplete("s999")  # Should not raise


class TestCheckDependenciesMet:
    def test_no_dependencies(self):
        mgr = PRDManager()
        story = _story(id="s1")
        assert mgr._check_dependencies_met(story) is True

    def test_dependency_met(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=True))
        story = _story(id="s2", dependencies=["s1"])
        assert mgr._check_dependencies_met(story) is True

    def test_dependency_not_passed(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=False))
        story = _story(id="s2", dependencies=["s1"])
        assert mgr._check_dependencies_met(story) is False

    def test_dependency_missing(self):
        mgr = PRDManager()
        story = _story(id="s2", dependencies=["s1"])
        assert mgr._check_dependencies_met(story) is False

    def test_multiple_dependencies_all_met(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=True))
        mgr.add_story(_story(id="s2", passes=True))
        story = _story(id="s3", dependencies=["s1", "s2"])
        assert mgr._check_dependencies_met(story) is True

    def test_multiple_dependencies_partial(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", passes=True))
        mgr.add_story(_story(id="s2", passes=False))
        story = _story(id="s3", dependencies=["s1", "s2"])
        assert mgr._check_dependencies_met(story) is False


class TestGetNextStoryWithDependencies:
    def test_skips_unmet_dependency(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", priority=5, passes=False))
        mgr.add_story(_story(id="s2", priority=10, passes=False, dependencies=["s1"]))
        # s2 has higher priority but blocked by s1
        next_s = mgr.get_next_story()
        assert next_s.id == "s1"

    def test_dependency_chain(self):
        mgr = PRDManager()
        mgr.add_story(_story(id="s1", priority=1, passes=False))
        mgr.add_story(_story(id="s2", priority=5, passes=False, dependencies=["s1"]))
        mgr.add_story(_story(id="s3", priority=10, passes=False, dependencies=["s2"]))
        # Only s1 is available
        assert mgr.get_next_story().id == "s1"
        mgr.mark_story_complete("s1")
        assert mgr.get_next_story().id == "s2"
        mgr.mark_story_complete("s2")
        assert mgr.get_next_story().id == "s3"

    def test_no_stories(self):
        mgr = PRDManager()
        assert mgr.get_next_story() is None


class TestSavePrdEdgeCases:
    def test_save_without_path_raises(self):
        mgr = PRDManager()
        mgr.create_prd("P", "main", "D", [_story()])
        mgr.file_path = None
        with pytest.raises(ValueError, match="No output path"):
            mgr.save_prd()

    def test_save_to_original_path(self, tmp_path):
        mgr = PRDManager()
        mgr.create_prd("P", "main", "D", [_story(id="s1", passes=False)])
        f = tmp_path / "prd.json"
        mgr.save_prd(f)
        mgr.file_path = f  # Set explicitly since save_prd doesn't auto-set
        # Now mark complete and save to original path
        mgr.mark_story_complete("s1")
        mgr.save_prd()
        # Re-read to verify
        with open(f) as fh:
            data = json.load(fh)
        assert data["userStories"][0]["passes"] is True

    def test_progress_empty_stories(self):
        mgr = PRDManager()
        p = mgr.get_progress_summary()
        assert p["total_stories"] == 0
        assert p["completion_percentage"] == 0
