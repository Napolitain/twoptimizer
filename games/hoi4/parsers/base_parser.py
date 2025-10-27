"""
Base parser for HOI4 game data files.

Provides common functionality for parsing various HOI4 data file formats.
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TextIO
from pathlib import Path


class ParseError(Exception):
    """Raised when there's an error parsing game data."""
    pass


class BaseParser(ABC):
    """
    Base class for all HOI4 data parsers.
    
    Provides common functionality for parsing HOI4's custom data format.
    """
    
    def __init__(self):
        self.data = {}
        self.current_file = None
        
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a single HOI4 data file.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Dictionary containing parsed data
            
        Raises:
            ParseError: If the file cannot be parsed
        """
        try:
            self.current_file = file_path
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return self._parse_content(content)
        except FileNotFoundError:
            raise ParseError(f"File not found: {file_path}")
        except Exception as e:
            raise ParseError(f"Error parsing {file_path}: {str(e)}")
    
    def parse_directory(self, directory_path: Path, pattern: str = "*.txt") -> Dict[str, Any]:
        """
        Parse all files matching pattern in a directory.
        
        Args:
            directory_path: Path to directory containing files
            pattern: File pattern to match (default: "*.txt")
            
        Returns:
            Dictionary containing all parsed data
        """
        all_data = {}
        
        for file_path in directory_path.glob(pattern):
            try:
                file_data = self.parse_file(file_path)
                all_data[file_path.stem] = file_data
            except ParseError as e:
                print(f"Warning: Failed to parse {file_path}: {e}")
                continue
                
        return all_data
    
    @abstractmethod
    def _parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse the content of a file. Must be implemented by subclasses.
        
        Args:
            content: File content as string
            
        Returns:
            Parsed data dictionary
        """
        pass
    
    def _clean_line(self, line: str) -> str:
        """
        Clean a line by removing comments and extra whitespace.
        
        Args:
            line: Raw line from file
            
        Returns:
            Cleaned line
        """
        # Remove comments (everything after #)
        if '#' in line:
            line = line[:line.index('#')]
        
        # Strip whitespace
        return line.strip()
    
    def _parse_block(self, lines: List[str], start_idx: int) -> tuple[Dict[str, Any], int]:
        """
        Parse a block structure (enclosed in braces).
        
        Args:
            lines: List of all lines
            start_idx: Index to start parsing from
            
        Returns:
            Tuple of (parsed_data, next_index)
        """
        block_data = {}
        i = start_idx
        
        while i < len(lines):
            line = self._clean_line(lines[i])
            
            if not line:
                i += 1
                continue
                
            if line == '}':
                return block_data, i + 1
                
            # Check for key-value pairs
            if '=' in line:
                key, value = self._parse_key_value(line, lines, i)
                if isinstance(value, dict) and key in block_data:
                    # Merge dictionaries for duplicate keys
                    if isinstance(block_data[key], dict):
                        block_data[key].update(value)
                    else:
                        block_data[key] = value
                else:
                    block_data[key] = value
                # Skip ahead if we parsed a nested block
                if isinstance(value, dict):
                    # Find the end of this block to continue parsing
                    brace_count = 1
                    j = i + 1
                    while j < len(lines) and brace_count > 0:
                        test_line = self._clean_line(lines[j])
                        if '{' in test_line:
                            brace_count += test_line.count('{')
                        if '}' in test_line:
                            brace_count -= test_line.count('}')
                        j += 1
                    i = j - 1
                    
            i += 1
            
        return block_data, i
    
    def _parse_key_value(self, line: str, lines: List[str], line_idx: int) -> tuple[str, Any]:
        """
        Parse a key-value pair, handling blocks and simple values.
        
        Args:
            line: Current line containing key=value
            lines: All lines (needed for multi-line blocks)
            line_idx: Current line index
            
        Returns:
            Tuple of (key, value)
        """
        parts = line.split('=', 1)
        if len(parts) != 2:
            return line.strip(), None
            
        key = parts[0].strip()
        value_part = parts[1].strip()
        
        # Handle block values
        if value_part == '{':
            block_data, _ = self._parse_block(lines, line_idx + 1)
            return key, block_data
        elif value_part.endswith('{'):
            # Handle "key = value {" format
            prefix_value = value_part[:-1].strip()
            block_data, _ = self._parse_block(lines, line_idx + 1)
            if prefix_value:
                return key, {prefix_value: block_data}
            return key, block_data
        else:
            # Handle simple values
            return key, self._parse_value(value_part)
    
    def _parse_value(self, value_str: str) -> Any:
        """
        Parse a value string into appropriate Python type.
        
        Args:
            value_str: String representation of value
            
        Returns:
            Parsed value (int, float, bool, or string)
        """
        value_str = value_str.strip()
        
        # Handle quoted strings
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        
        # Handle booleans
        if value_str.lower() in ('yes', 'true'):
            return True
        elif value_str.lower() in ('no', 'false'):
            return False
            
        # Handle numbers
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
            
        # Return as string if nothing else matches
        return value_str
    
    def _split_lines(self, content: str) -> List[str]:
        """
        Split content into lines, handling various line endings.
        
        Args:
            content: File content
            
        Returns:
            List of lines
        """
        # Handle different line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        return content.split('\n')
