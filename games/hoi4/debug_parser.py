"""
Debug script to check file parsing.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4.parsers.base_parser import BaseParser


class DebugParser(BaseParser):
    def _parse_content(self, content: str) -> dict:
        lines = self._split_lines(content)
        print(f"Total lines: {len(lines)}")
        
        for i, line in enumerate(lines[:20]):  # Show first 20 lines
            cleaned = self._clean_line(line)
            print(f"Line {i}: '{line}' -> '{cleaned}'")
        
        return {}


def main():
    parser = DebugParser()
    
    file_path = Path("games/hoi4/data/buildings/00_buildings.txt")
    if file_path.exists():
        print(f"Parsing {file_path}")
        result = parser.parse_file(file_path)
    else:
        print(f"File not found: {file_path}")


if __name__ == "__main__":
    main()
