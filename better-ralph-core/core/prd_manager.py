"""
PRD Manager - Product Requirements Document management.

Handles loading, parsing, and managing PRD stories and their state.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict

from utils.logger import Logger


@dataclass
class UserStory:
    """Represents a single user story in the PRD."""
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
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserStory':
        """Create from dictionary."""
        return cls(**data)


class PRDManager:
    """
    Manages Product Requirements Document (PRD) stories and their state.
    
    Handles loading PRD files, managing story states, and providing methods
    to track progress and manage stories.
    """
    
    def __init__(self):
        """Initialize the PRD manager."""
        self.logger = Logger.get_logger("prd_manager")
        self.prd_data: Dict[str, Any] = {}
        self.stories: List[UserStory] = []
        self.file_path: Optional[Path] = None
        
        self.logger.info("PRD Manager initialized")
    
    def load_prd(self, prd_path: Path) -> None:
        """
        Load PRD from a JSON file.
        
        Args:
            prd_path: Path to the PRD JSON file
        """
        self.file_path = prd_path
        
        try:
            with open(prd_path, 'r', encoding='utf-8') as f:
                self.prd_data = json.load(f)
            
            # Parse stories
            self.stories = []
            for story_data in self.prd_data.get("userStories", []):
                story = UserStory.from_dict(story_data)
                self.stories.append(story)
            
            self.logger.info(f"Loaded PRD from {prd_path}: {len(self.stories)} stories")
            
        except FileNotFoundError:
            self.logger.error(f"PRD file not found: {prd_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in PRD file: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading PRD: {e}")
            raise
    
    def create_prd(self, project_name: str, branch_name: str, description: str, 
                  stories: List[UserStory]) -> None:
        """
        Create a new PRD with the given stories.
        
        Args:
            project_name: Name of the project
            branch_name: Git branch name
            description: Short project description
            stories: List of user stories
        """
        self.prd_data = {
            "project": project_name,
            "branchName": branch_name,
            "description": description,
            "userStories": [story.to_dict() for story in stories],
            "createdAt": datetime.now().isoformat()
        }
        
        self.stories = stories
        self.logger.info(f"Created new PRD with {len(stories)} stories")
    
    def save_prd(self, output_path: Optional[Path] = None) -> None:
        """
        Save the current PRD to a file.
        
        Args:
            output_path: Optional output path. If None, uses original path.
        """
        save_path = output_path or self.file_path
        
        if not save_path:
            raise ValueError("No output path specified")
        
        try:
            # Update story data in prd_data
            self.prd_data["userStories"] = [story.to_dict() for story in self.stories]
            self.prd_data["updatedAt"] = datetime.now().isoformat()
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.prd_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved PRD to {save_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving PRD: {e}")
            raise
    
    def get_all_stories(self) -> List[UserStory]:
        """Get all user stories."""
        return self.stories
    
    def get_story_by_id(self, story_id: str) -> Optional[UserStory]:
        """Get a specific user story by ID."""
        for story in self.stories:
            if story.id == story_id:
                return story
        return None
    
    def get_next_story(self) -> Optional[UserStory]:
        """
        Get the next highest priority incomplete story.
        
        Returns:
            The next story to work on, or None if all stories are complete
        """
        # Filter incomplete stories
        incomplete_stories = [s for s in self.stories if not s.passes]
        
        if not incomplete_stories:
            return None
        
        # Sort by priority (lower number = higher priority)
        incomplete_stories.sort(key=lambda s: s.priority)
        
        # Check dependencies
        next_story = incomplete_stories[0]
        
        # Check if this story's dependencies are met
        if not self._check_dependencies_met(next_story):
            # Find next story without dependencies or with met dependencies
            for story in incomplete_stories[1:]:
                if self._check_dependencies_met(story):
                    next_story = story
                    break
        
        return next_story
    
    def _check_dependencies_met(self, story: UserStory) -> bool:
        """Check if all dependencies for a story are met."""
        if not story.dependencies:
            return True
        
        for dep_id in story.dependencies:
            dep_story = self.get_story_by_id(dep_id)
            if not dep_story or not dep_story.passes:
                return False
        
        return True
    
    def mark_story_complete(self, story_id: str) -> None:
        """
        Mark a story as complete.
        
        Args:
            story_id: ID of the story to mark complete
        """
        story = self.get_story_by_id(story_id)
        if story:
            story.passes = True
            self.logger.info(f"Marked story {story_id} as complete")
        else:
            self.logger.warning(f"Story {story_id} not found for marking complete")
    
    def mark_story_incomplete(self, story_id: str) -> None:
        """
        Mark a story as incomplete.
        
        Args:
            story_id: ID of the story to mark incomplete
        """
        story = self.get_story_by_id(story_id)
        if story:
            story.passes = False
            self.logger.info(f"Marked story {story_id} as incomplete")
        else:
            self.logger.warning(f"Story {story_id} not found for marking incomplete")
    
    def add_story(self, story: UserStory) -> None:
        """
        Add a new story to the PRD.
        
        Args:
            story: User story to add
        """
        self.stories.append(story)
        self.logger.info(f"Added story {story.id} to PRD")
    
    def remove_story(self, story_id: str) -> bool:
        """
        Remove a story from the PRD.
        
        Args:
            story_id: ID of the story to remove
            
        Returns:
            True if story was removed, False if not found
        """
        for i, story in enumerate(self.stories):
            if story.id == story_id:
                del self.stories[i]
                self.logger.info(f"Removed story {story_id} from PRD")
                return True
        
        self.logger.warning(f"Story {story_id} not found for removal")
        return False
    
    def update_story(self, story_id: str, **kwargs) -> bool:
        """
        Update a story with new values.
        
        Args:
            story_id: ID of the story to update
            **kwargs: Fields to update
            
        Returns:
            True if story was updated, False if not found
        """
        story = self.get_story_by_id(story_id)
        if story:
            for key, value in kwargs.items():
                if hasattr(story, key):
                    setattr(story, key, value)
            
            self.logger.info(f"Updated story {story_id}")
            return True
        
        self.logger.warning(f"Story {story_id} not found for update")
        return False
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get a summary of PRD progress."""
        total_stories = len(self.stories)
        completed_stories = sum(1 for s in self.stories if s.passes)
        
        # Calculate priority distribution
        priority_stats = {}
        for story in self.stories:
            priority = story.priority
            if priority not in priority_stats:
                priority_stats[priority] = {"total": 0, "completed": 0}
            
            priority_stats[priority]["total"] += 1
            if story.passes:
                priority_stats[priority]["completed"] += 1
        
        return {
            "total_stories": total_stories,
            "completed_stories": completed_stories,
            "progress_percentage": (completed_stories / total_stories) * 100 if total_stories > 0 else 0,
            "priority_distribution": priority_stats,
            "completed_stories_list": [s.id for s in self.stories if s.passes],
            "remaining_stories": [s.id for s in self.stories if not s.passes]
        }
    
    def split_large_story(self, story_id: str, max_criteria: int = 3) -> List[UserStory]:
        """
        Split a large story into smaller stories based on acceptance criteria.
        
        Args:
            story_id: ID of the story to split
            max_criteria: Maximum criteria per story
            
        Returns:
            List of new stories created
        """
        original_story = self.get_story_by_id(story_id)
        if not original_story:
            self.logger.warning(f"Story {story_id} not found for splitting")
            return []
        
        # Remove original story
        self.remove_story(story_id)
        
        # Create new stories
        new_stories = []
        criteria_chunks = self._chunk_list(original_story.acceptance_criteria, max_criteria)
        
        for i, criteria_chunk in enumerate(criteria_chunks):
            new_story = UserStory(
                id=f"{story_id}-{i+1}",
                title=f"{original_story.title} (Part {i+1})",
                description=original_story.description,
                acceptance_criteria=criteria_chunk,
                priority=original_story.priority,
                passes=False,
                notes=original_story.notes,
                estimated_hours=original_story.estimated_hours / len(criteria_chunks) if original_story.estimated_hours else None,
                dependencies=original_story.dependencies
            )
            new_stories.append(new_story)
            self.add_story(new_story)
        
        self.logger.info(f"Split story {story_id} into {len(new_stories)} smaller stories")
        return new_stories
    
    def _chunk_list(self, lst: List[str], size: int) -> List[List[str]]:
        """Split a list into chunks of specified size."""
        return [lst[i:i + size] for i in range(0, len(lst), size)]
    
    def auto_adjust_priorities(self) -> None:
        """
        Automatically adjust story priorities based on dependencies and completion status.
        """
        # Build dependency graph
        dependency_graph = {}
        for story in self.stories:
            dependency_graph[story.id] = story.dependencies
        
        # Calculate dependency depth for each story
        dependency_depths = {}
        for story_id in dependency_graph:
            depth = self._calculate_dependency_depth(story_id, dependency_graph)
            dependency_depths[story_id] = depth
        
        # Adjust priorities based on dependency depth
        for story in self.stories:
            if not story.passes:
                # Increase priority (lower number) for stories with deeper dependencies
                base_priority = 1
                depth_bonus = min(dependency_depths.get(story.id, 0), 5)
                new_priority = base_priority + depth_bonus
                
                if new_priority != story.priority:
                    story.priority = new_priority
                    self.logger.info(f"Adjusted priority for story {story.id}: {story.priority}")
    
    def _calculate_dependency_depth(self, story_id: str, dependency_graph: Dict[str, List[str]], 
                                   visited: Optional[Set[str]] = None) -> int:
        """Calculate the maximum depth of dependencies for a story."""
        if visited is None:
            visited = set()
        
        if story_id in visited:
            return 0  # Circular dependency
        
        visited.add(story_id)
        
        if story_id not in dependency_graph or not dependency_graph[story_id]:
            return 0
        
        max_depth = 0
        for dep_id in dependency_graph[story_id]:
            depth = self._calculate_dependency_depth(dep_id, dependency_graph, visited.copy())
            max_depth = max(max_depth, depth + 1)
        
        return max_depth