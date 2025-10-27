"""
Idea parser for HOI4 national ideas.

Parses idea data from games/hoi4/data/ideas/*.txt files.
"""

from typing import Dict, Any, List
from pathlib import Path
from games.hoi4.parsers.base_parser import BaseParser, ParseError
from games.hoi4.models.idea import Idea, IdeaCategory


class IdeaParser(BaseParser):
    """
    Parser for HOI4 idea definition files.
    
    Extracts national ideas including laws, national spirits, and advisors.
    """
    
    def __init__(self):
        super().__init__()
        self.ideas: Dict[str, Idea] = {}
    
    def _parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse idea file content.
        
        Args:
            content: File content as string
            
        Returns:
            Dictionary of idea definitions
        """
        lines = self._split_lines(content)
        parsed_data = {}
        
        i = 0
        while i < len(lines):
            line = self._clean_line(lines[i])
            
            if not line:
                i += 1
                continue
                
            # Look for main "ideas" block
            if line.startswith('ideas') and '=' in line:
                if line.endswith('{'):
                    # Handle "ideas = {" format
                    block_data, next_i = self._parse_block(lines, i + 1)
                    parsed_data['ideas'] = block_data
                    i = next_i
                else:
                    # Handle "ideas = { ... }" on same line or with separate brace
                    _, value = self._parse_key_value(line, lines, i)
                    if isinstance(value, dict):
                        parsed_data['ideas'] = value
                    i += 1
                break
                
            i += 1
        
        # Process and clean up idea data
        if 'ideas' in parsed_data:
            self.ideas = self._process_ideas(parsed_data['ideas'])
        else:
            print(f"Warning: No 'ideas' block found in file {self.current_file}")
            
        return self.ideas
    
    def _process_ideas(self, ideas_data: Dict[str, Any]) -> Dict[str, Idea]:
        """
        Process raw idea data into Idea objects.
        
        Args:
            ideas_data: Raw idea data from parser
            
        Returns:
            Dictionary of idea name -> Idea object
        """
        processed = {}
        
        for category_name, category_data in ideas_data.items():
            if not isinstance(category_data, dict):
                continue
            
            # Determine the category
            idea_category = self._determine_category(category_name)
            
            # Process each idea in this category
            for idea_name, idea_data in category_data.items():
                if not isinstance(idea_data, dict):
                    continue
                
                # Skip non-idea keys like "law", "use_list_view", etc.
                if idea_name in ['law', 'use_list_view', 'designer', 'visible']:
                    continue
                
                idea = self._process_single_idea(idea_name, idea_data, idea_category)
                if idea:
                    processed[idea_name] = idea
        
        return processed
    
    def _determine_category(self, category_name: str) -> IdeaCategory:
        """
        Determine the IdeaCategory from a category name string.
        
        Args:
            category_name: Category name from the data file
            
        Returns:
            Corresponding IdeaCategory enum value
        """
        category_map = {
            'country': IdeaCategory.COUNTRY,
            'economy': IdeaCategory.ECONOMY,
            'trade_laws': IdeaCategory.TRADE,
            'mobilization_laws': IdeaCategory.MANPOWER,
            'political_advisor': IdeaCategory.POLITICAL_ADVISOR,
            'army_chief': IdeaCategory.ARMY_CHIEF,
            'navy_chief': IdeaCategory.NAVY_CHIEF,
            'air_chief': IdeaCategory.AIR_CHIEF,
            'high_command': IdeaCategory.HIGH_COMMAND,
            'theorist': IdeaCategory.THEORIST,
            'tank_manufacturer': IdeaCategory.TANK_MANUFACTURER,
            'naval_manufacturer': IdeaCategory.NAVAL_MANUFACTURER,
            'aircraft_manufacturer': IdeaCategory.AIRCRAFT_MANUFACTURER,
            'materiel_manufacturer': IdeaCategory.MATERIEL_MANUFACTURER,
            'industrial_concern': IdeaCategory.INDUSTRIAL_CONCERN,
        }
        
        return category_map.get(category_name, IdeaCategory.COUNTRY)
    
    def _process_single_idea(self, name: str, data: Dict[str, Any], category: IdeaCategory) -> Idea:
        """
        Process a single idea definition.
        
        Args:
            name: Idea name
            data: Raw idea data
            category: Category of this idea
            
        Returns:
            Idea object
        """
        # Extract modifier data
        modifier = {}
        if 'modifier' in data and isinstance(data['modifier'], dict):
            for key, value in data['modifier'].items():
                if isinstance(value, (int, float)):
                    modifier[key] = float(value)
        
        # Extract other attributes
        cost = data.get('cost', 0)
        if isinstance(cost, (int, float)):
            cost = int(cost)
        else:
            cost = 0
        
        removal_cost = data.get('removal_cost', -1)
        if isinstance(removal_cost, (int, float)):
            removal_cost = int(removal_cost)
        else:
            removal_cost = -1
        
        level = data.get('level', 0)
        if isinstance(level, (int, float)):
            level = int(level)
        else:
            level = 0
        
        # Create the Idea object
        idea = Idea(
            name=name,
            category=category,
            cost=cost,
            removal_cost=removal_cost,
            level=level,
            allowed=data.get('allowed', {}),
            available=data.get('available', {}),
            modifier=modifier,
            rule=data.get('rule', {}),
            allowed_civil_war=data.get('allowed_civil_war'),
            cancel_if_invalid=data.get('cancel_if_invalid', True),
            picture=data.get('picture')
        )
        
        return idea
    
    def get_idea(self, idea_name: str) -> Idea:
        """
        Get a specific idea definition.
        
        Args:
            idea_name: Name of the idea
            
        Returns:
            Idea object
            
        Raises:
            KeyError: If idea is not found
        """
        if idea_name not in self.ideas:
            raise KeyError(f"Idea '{idea_name}' not found")
        return self.ideas[idea_name]
    
    def get_all_ideas(self) -> Dict[str, Idea]:
        """
        Get all idea definitions.
        
        Returns:
            Dictionary of all idea definitions
        """
        return self.ideas.copy()
    
    def get_ideas_by_category(self, category: IdeaCategory) -> Dict[str, Idea]:
        """
        Get ideas filtered by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            Dictionary of matching ideas
        """
        return {
            name: idea
            for name, idea in self.ideas.items()
            if idea.category == category
        }
    
    def get_laws(self) -> Dict[str, Idea]:
        """
        Get all law ideas (economy, trade, manpower).
        
        Returns:
            Dictionary of law ideas
        """
        laws = {}
        for category in [IdeaCategory.ECONOMY, IdeaCategory.TRADE, IdeaCategory.MANPOWER]:
            laws.update(self.get_ideas_by_category(category))
        return laws
    
    def get_national_spirits(self) -> Dict[str, Idea]:
        """
        Get all national spirit ideas.
        
        Returns:
            Dictionary of national spirit ideas
        """
        return self.get_ideas_by_category(IdeaCategory.COUNTRY)
