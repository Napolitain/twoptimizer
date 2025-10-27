"""
Focus tree parser for HOI4 national focus trees.

Parses national focus data from games/hoi4/data/national_focus/*.txt files.
"""

from typing import Dict, Any, List
from pathlib import Path
from games.hoi4.parsers.base_parser import BaseParser, ParseError
from games.hoi4.models.focus import Focus, FocusTree, FocusFilterCategory


class FocusParser(BaseParser):
    """
    Parser for HOI4 national focus tree files.
    
    Extracts focus tree structure and individual focuses.
    """
    
    def __init__(self):
        super().__init__()
        self.focus_trees: Dict[str, FocusTree] = {}
    
    def _parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse focus tree file content.
        
        Args:
            content: File content as string
            
        Returns:
            Dictionary of focus tree definitions
        """
        lines = self._split_lines(content)
        parsed_data = {}
        
        i = 0
        while i < len(lines):
            line = self._clean_line(lines[i])
            
            if not line:
                i += 1
                continue
                
            # Look for main "focus_tree" block
            if line.startswith('focus_tree') and '=' in line:
                if line.endswith('{'):
                    block_data, next_i = self._parse_block(lines, i + 1)
                    parsed_data['focus_tree'] = block_data
                    i = next_i
                else:
                    _, value = self._parse_key_value(line, lines, i)
                    if isinstance(value, dict):
                        parsed_data['focus_tree'] = value
                    i += 1
                break
                
            i += 1
        
        # Process focus tree data
        if 'focus_tree' in parsed_data:
            tree = self._process_focus_tree(parsed_data['focus_tree'])
            if tree:
                self.focus_trees[tree.id] = tree
        else:
            print(f"Warning: No 'focus_tree' block found in file {self.current_file}")
            
        return self.focus_trees
    
    def _process_focus_tree(self, tree_data: Dict[str, Any]) -> FocusTree:
        """
        Process raw focus tree data into FocusTree object.
        
        Args:
            tree_data: Raw tree data from parser
            
        Returns:
            FocusTree object
        """
        # Extract tree ID
        tree_id = tree_data.get('id', 'unknown')
        
        # Create focus tree
        tree = FocusTree(
            id=tree_id,
            default=tree_data.get('default', False)
        )
        
        # Extract country tags
        if 'country' in tree_data and isinstance(tree_data['country'], dict):
            country_data = tree_data['country']
            if 'modifier' in country_data and isinstance(country_data['modifier'], dict):
                modifier = country_data['modifier']
                if 'tag' in modifier:
                    tag = modifier['tag']
                    if isinstance(tag, str):
                        tree.country_tags.append(tag)
                    elif isinstance(tag, list):
                        tree.country_tags.extend(tag)
        
        # Extract continuous focus position
        if 'continuous_focus_position' in tree_data:
            pos = tree_data['continuous_focus_position']
            if isinstance(pos, dict):
                tree.continuous_focus_position = pos
        
        # Extract shared focuses
        if 'shared_focus' in tree_data:
            shared = tree_data['shared_focus']
            if isinstance(shared, str):
                tree.shared_focuses.append(shared)
            elif isinstance(shared, list):
                tree.shared_focuses.extend(shared)
        
        # Process individual focuses
        focuses_found = []
        for key, value in tree_data.items():
            if key == 'focus' and isinstance(value, dict):
                # Single focus or multiple focuses stored by ID
                for focus_id, focus_data in value.items():
                    if isinstance(focus_data, dict):
                        # Add the ID if not already in the data
                        if 'id' not in focus_data:
                            focus_data['id'] = focus_id
                        focus = self._process_focus(focus_data)
                        if focus:
                            tree.add_focus(focus)
                            focuses_found.append(focus.id)
        
        # If no focuses found with the above method, try the list approach
        if not focuses_found and 'focus' in tree_data:
            focus_list = tree_data['focus']
            # Handle case where it's already a list
            if isinstance(focus_list, list):
                for focus_data in focus_list:
                    if isinstance(focus_data, dict):
                        focus = self._process_focus(focus_data)
                        if focus:
                            tree.add_focus(focus)
        
        return tree
    
    def _process_focus(self, focus_data: Dict[str, Any]) -> Focus:
        """
        Process a single focus definition.
        
        Args:
            focus_data: Raw focus data
            
        Returns:
            Focus object
        """
        # Extract basic attributes
        focus_id = focus_data.get('id', 'unknown')
        icon = focus_data.get('icon', '')
        x = focus_data.get('x', 0)
        y = focus_data.get('y', 0)
        cost = focus_data.get('cost', 10)
        
        # Handle type conversions
        if isinstance(x, (int, float)):
            x = int(x)
        else:
            x = 0
        
        if isinstance(y, (int, float)):
            y = int(y)
        else:
            y = 0
        
        if isinstance(cost, (int, float)):
            cost = int(cost)
        else:
            cost = 10
        
        # Extract prerequisites
        prerequisites = []
        if 'prerequisite' in focus_data:
            prereq_data = focus_data['prerequisite']
            prerequisites = self._extract_focus_list(prereq_data, 'focus')
        
        # Extract mutually exclusive
        mutually_exclusive = []
        if 'mutually_exclusive' in focus_data:
            mutex_data = focus_data['mutually_exclusive']
            mutually_exclusive = self._extract_focus_list(mutex_data, 'focus')
        
        # Extract search filters
        search_filters = []
        if 'search_filters' in focus_data:
            filters = focus_data['search_filters']
            if isinstance(filters, dict):
                for filter_name in filters.keys():
                    try:
                        category = FocusFilterCategory(filter_name)
                        search_filters.append(category)
                    except ValueError:
                        pass  # Skip unknown categories
        
        # Create Focus object
        focus = Focus(
            id=focus_id,
            icon=icon,
            x=x,
            y=y,
            cost=cost,
            prerequisites=prerequisites,
            mutually_exclusive=mutually_exclusive,
            relative_position_id=focus_data.get('relative_position_id'),
            available=focus_data.get('available', {}),
            bypass=focus_data.get('bypass', {}),
            cancel_if_invalid=focus_data.get('cancel_if_invalid', True),
            completion_reward=focus_data.get('completion_reward', {}),
            ai_will_do=focus_data.get('ai_will_do', {}),
            search_filters=search_filters,
            available_if_capitulated=focus_data.get('available_if_capitulated', False),
            continue_if_invalid=focus_data.get('continue_if_invalid', False),
            allow_branch=focus_data.get('allow_branch', {})
        )
        
        return focus
    
    def _extract_focus_list(self, data: Any, key: str = 'focus') -> List[str]:
        """
        Extract a list of focus IDs from prerequisite or mutex data.
        
        Args:
            data: Raw data (can be dict, list, or str)
            key: Key to look for focus IDs
            
        Returns:
            List of focus IDs
        """
        focus_ids = []
        
        if isinstance(data, str):
            focus_ids.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and key in item:
                    # Recursively extract from nested structure
                    nested_ids = self._extract_focus_list(item[key], key)
                    focus_ids.extend(nested_ids)
                elif isinstance(item, str):
                    focus_ids.append(item)
        elif isinstance(data, dict):
            if key in data:
                # Recursively extract from nested structure
                nested_ids = self._extract_focus_list(data[key], key)
                focus_ids.extend(nested_ids)
            else:
                # If no 'focus' key, treat dict keys as focus IDs if they look like IDs
                for k, v in data.items():
                    if isinstance(k, str) and not k.startswith('_'):
                        focus_ids.append(k)
        
        return focus_ids
    
    def get_focus_tree(self, tree_id: str) -> FocusTree:
        """
        Get a specific focus tree by ID.
        
        Args:
            tree_id: ID of the focus tree
            
        Returns:
            FocusTree object
            
        Raises:
            KeyError: If tree is not found
        """
        if tree_id not in self.focus_trees:
            raise KeyError(f"Focus tree '{tree_id}' not found")
        return self.focus_trees[tree_id]
    
    def get_all_focus_trees(self) -> Dict[str, FocusTree]:
        """
        Get all parsed focus trees.
        
        Returns:
            Dictionary of tree_id -> FocusTree
        """
        return self.focus_trees.copy()
    
    def get_focus_tree_by_country(self, country_tag: str) -> List[FocusTree]:
        """
        Get all focus trees for a specific country.
        
        Args:
            country_tag: Country tag (e.g., "GER", "SOV")
            
        Returns:
            List of FocusTree objects
        """
        return [
            tree for tree in self.focus_trees.values()
            if country_tag in tree.country_tags
        ]
