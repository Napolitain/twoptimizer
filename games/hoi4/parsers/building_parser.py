"""
Building parser for HOI4 building definitions.

Parses building data from games/hoi4/data/buildings/*.txt files.
"""

from typing import Dict, Any, List
from pathlib import Path
from .base_parser import BaseParser, ParseError


class BuildingParser(BaseParser):
    """
    Parser for HOI4 building definition files.
    
    Extracts building information including costs, effects, and requirements.
    """
    
    def __init__(self):
        super().__init__()
        self.buildings = {}
    
    def _parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse building file content.
        
        Args:
            content: File content as string
            
        Returns:
            Dictionary of building definitions
        """
        lines = self._split_lines(content)
        parsed_data = {}
        
        i = 0
        while i < len(lines):
            line = self._clean_line(lines[i])
            
            if not line:
                i += 1
                continue
                
            # Look for main "buildings" block
            if line.startswith('buildings') and '=' in line:
                if line.endswith('{'):
                    # Handle "buildings = {" format
                    block_data, next_i = self._parse_block(lines, i + 1)
                    parsed_data['buildings'] = block_data
                    i = next_i
                else:
                    # Handle "buildings = { ... }" on same line or with separate brace
                    _, value = self._parse_key_value(line, lines, i)
                    if isinstance(value, dict):
                        parsed_data['buildings'] = value
                    i += 1
                break
                
            i += 1
        
        # Process and clean up building data
        if 'buildings' in parsed_data:
            self.buildings = self._process_buildings(parsed_data['buildings'])
        else:
            print("Warning: No 'buildings' block found in file")
            
        return self.buildings
    
    def _process_buildings(self, buildings_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Process raw building data into a cleaner format.
        
        Args:
            buildings_data: Raw building data from parser
            
        Returns:
            Processed building definitions
        """
        processed = {}
        
        for building_name, building_info in buildings_data.items():
            if not isinstance(building_info, dict):
                continue
                
            processed[building_name] = self._process_single_building(building_name, building_info)
            
        return processed
    
    def _process_single_building(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single building definition.
        
        Args:
            name: Building name
            data: Raw building data
            
        Returns:
            Processed building definition
        """
        building = {
            'name': name,
            'base_cost': data.get('base_cost', 0),
            'icon_frame': data.get('icon_frame', 0),
            'infrastructure': data.get('infrastructure', False),
            'max_level': data.get('max_level', None),
            'show_on_map': data.get('show_on_map', None),
            'province_max': data.get('province_max', None),
            'country_modifiers': {},
            'state_modifiers': {},
            'level_cap': {},
            'construction_effects': {},
            'repair_speed_factor': data.get('repair_speed_factor', 1.0),
        }
        
        # Process level cap
        if 'level_cap' in data and isinstance(data['level_cap'], dict):
            building['level_cap'] = data['level_cap']
        
        # Process country modifiers
        if 'country_modifiers' in data and isinstance(data['country_modifiers'], dict):
            building['country_modifiers'] = self._process_modifiers(data['country_modifiers'])
        
        # Process state modifiers
        if 'state_modifiers' in data and isinstance(data['state_modifiers'], dict):
            building['state_modifiers'] = self._process_modifiers(data['state_modifiers'])
        
        # Process construction effects
        construction_effects = [
            'infrastructure_construction_effect',
            'military_factory_construction_effect',
            'civilian_factory_construction_effect',
            'naval_construction_effect'
        ]
        
        for effect in construction_effects:
            if data.get(effect):
                building['construction_effects'][effect] = True
        
        return building
    
    def _process_modifiers(self, modifiers_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process modifier data.
        
        Args:
            modifiers_data: Raw modifier data
            
        Returns:
            Processed modifiers
        """
        processed = {}
        
        # Handle enable_for_controllers
        if 'enable_for_controllers' in modifiers_data:
            processed['enable_for_controllers'] = modifiers_data['enable_for_controllers']
        
        # Handle modifiers block
        if 'modifiers' in modifiers_data and isinstance(modifiers_data['modifiers'], dict):
            processed['modifiers'] = modifiers_data['modifiers']
        
        return processed
    
    def get_building(self, building_name: str) -> Dict[str, Any]:
        """
        Get a specific building definition.
        
        Args:
            building_name: Name of the building
            
        Returns:
            Building definition dictionary
            
        Raises:
            KeyError: If building is not found
        """
        if building_name not in self.buildings:
            raise KeyError(f"Building '{building_name}' not found")
        return self.buildings[building_name]
    
    def get_all_buildings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all building definitions.
        
        Returns:
            Dictionary of all building definitions
        """
        return self.buildings.copy()
    
    def get_buildings_by_type(self, building_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get buildings filtered by type/category.
        
        Args:
            building_type: Type of building to filter by
            
        Returns:
            Dictionary of matching buildings
        """
        # This could be enhanced based on building categories
        # For now, return buildings that match certain criteria
        filtered = {}
        
        for name, building in self.buildings.items():
            if building_type.lower() in name.lower():
                filtered[name] = building
                
        return filtered
    
    def get_factory_buildings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all factory-type buildings.
        
        Returns:
            Dictionary of factory buildings
        """
        factory_types = ['industrial_complex', 'arms_factory', 'dockyard']
        factories = {}
        
        for name, building in self.buildings.items():
            if any(factory_type in name for factory_type in factory_types):
                factories[name] = building
                
        return factories
    
    def get_infrastructure_buildings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all infrastructure-type buildings.
        
        Returns:
            Dictionary of infrastructure buildings
        """
        infrastructure = {}
        
        for name, building in self.buildings.items():
            if building.get('infrastructure') or 'infrastructure' in name:
                infrastructure[name] = building
                
        return infrastructure
