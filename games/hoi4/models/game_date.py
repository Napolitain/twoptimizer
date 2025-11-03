"""
Game date and time management for HOI4.

Provides classes for tracking game time and managing time-based calculations.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class GameDate:
    """
    Represents a date in Hearts of Iron IV.
    
    HOI4 starts in 1936 and typically runs through the 1940s-1950s.
    Game time is measured in days.
    
    Attributes:
        year: Calendar year
        month: Calendar month (1-12)
        day: Calendar day (1-31)
        hour: Hour of day (0-23), optional for precision
    """
    year: int
    month: int
    day: int
    hour: int = 0
    
    def __post_init__(self):
        """Validate date components."""
        if not 1936 <= self.year <= 1970:
            raise ValueError(f"Year must be between 1936 and 1970, got {self.year}")
        if not 1 <= self.month <= 12:
            raise ValueError(f"Month must be between 1 and 12, got {self.month}")
        if not 1 <= self.day <= 31:
            raise ValueError(f"Day must be between 1 and 31, got {self.day}")
        if not 0 <= self.hour <= 23:
            raise ValueError(f"Hour must be between 0 and 23, got {self.hour}")
    
    def to_datetime(self) -> datetime:
        """
        Convert to Python datetime object.
        
        Returns:
            datetime representation of this game date
        """
        return datetime(self.year, self.month, self.day, self.hour)
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> 'GameDate':
        """
        Create GameDate from Python datetime.
        
        Args:
            dt: datetime object
            
        Returns:
            GameDate instance
        """
        return cls(year=dt.year, month=dt.month, day=dt.day, hour=dt.hour)
    
    def add_days(self, days: int) -> 'GameDate':
        """
        Add days to this date.
        
        Args:
            days: Number of days to add (can be negative)
            
        Returns:
            New GameDate with days added
        """
        dt = self.to_datetime() + timedelta(days=days)
        return GameDate.from_datetime(dt)
    
    def add_hours(self, hours: int) -> 'GameDate':
        """
        Add hours to this date.
        
        Args:
            hours: Number of hours to add (can be negative)
            
        Returns:
            New GameDate with hours added
        """
        dt = self.to_datetime() + timedelta(hours=hours)
        return GameDate.from_datetime(dt)
    
    def days_until(self, other: 'GameDate') -> int:
        """
        Calculate days between this date and another.
        
        Args:
            other: Target date
            
        Returns:
            Number of days (negative if other is before this date)
        """
        delta = other.to_datetime() - self.to_datetime()
        return delta.days
    
    def hours_until(self, other: 'GameDate') -> int:
        """
        Calculate hours between this date and another.
        
        Args:
            other: Target date
            
        Returns:
            Number of hours (negative if other is before this date)
        """
        delta = other.to_datetime() - self.to_datetime()
        return int(delta.total_seconds() / 3600)
    
    def __lt__(self, other: 'GameDate') -> bool:
        """Compare if this date is before another."""
        return self.to_datetime() < other.to_datetime()
    
    def __le__(self, other: 'GameDate') -> bool:
        """Compare if this date is before or equal to another."""
        return self.to_datetime() <= other.to_datetime()
    
    def __gt__(self, other: 'GameDate') -> bool:
        """Compare if this date is after another."""
        return self.to_datetime() > other.to_datetime()
    
    def __ge__(self, other: 'GameDate') -> bool:
        """Compare if this date is after or equal to another."""
        return self.to_datetime() >= other.to_datetime()
    
    def __eq__(self, other: object) -> bool:
        """Check if two dates are equal."""
        if not isinstance(other, GameDate):
            return False
        return (self.year == other.year and 
                self.month == other.month and 
                self.day == other.day and 
                self.hour == other.hour)
    
    def __str__(self) -> str:
        """String representation of the date."""
        if self.hour > 0:
            return f"{self.year}.{self.month:02d}.{self.day:02d} {self.hour:02d}:00"
        return f"{self.year}.{self.month:02d}.{self.day:02d}"
    
    def __repr__(self) -> str:
        return f"GameDate({self.year}, {self.month}, {self.day}, {self.hour})"


class GameClock:
    """
    Manages game time progression and scheduling.
    
    Provides functionality for advancing time and tracking elapsed days.
    """
    
    def __init__(self, start_date: Optional[GameDate] = None):
        """
        Initialize game clock.
        
        Args:
            start_date: Starting date (defaults to Jan 1, 1936)
        """
        self.start_date = start_date or GameDate(1936, 1, 1)
        self.current_date = GameDate(
            self.start_date.year, 
            self.start_date.month, 
            self.start_date.day,
            self.start_date.hour
        )
    
    def advance_days(self, days: int) -> GameDate:
        """
        Advance the clock by a number of days.
        
        Args:
            days: Number of days to advance
            
        Returns:
            New current date
        """
        if days < 0:
            raise ValueError("Cannot advance by negative days")
        self.current_date = self.current_date.add_days(days)
        return self.current_date
    
    def advance_hours(self, hours: int) -> GameDate:
        """
        Advance the clock by a number of hours.
        
        Args:
            hours: Number of hours to advance
            
        Returns:
            New current date
        """
        if hours < 0:
            raise ValueError("Cannot advance by negative hours")
        self.current_date = self.current_date.add_hours(hours)
        return self.current_date
    
    def advance_to_date(self, target_date: GameDate) -> int:
        """
        Advance the clock to a specific date.
        
        Args:
            target_date: Target date to advance to
            
        Returns:
            Number of days advanced
            
        Raises:
            ValueError: If target date is before current date
        """
        days = self.current_date.days_until(target_date)
        if days < 0:
            raise ValueError(f"Target date {target_date} is before current date {self.current_date}")
        
        self.current_date = GameDate(
            target_date.year,
            target_date.month,
            target_date.day,
            target_date.hour
        )
        return days
    
    def elapsed_days(self) -> int:
        """
        Get the number of days elapsed since start.
        
        Returns:
            Days elapsed
        """
        return self.start_date.days_until(self.current_date)
    
    def reset(self) -> None:
        """Reset clock to start date."""
        self.current_date = GameDate(
            self.start_date.year,
            self.start_date.month,
            self.start_date.day,
            self.start_date.hour
        )
    
    def set_date(self, date: GameDate) -> None:
        """
        Set the current date directly.
        
        Args:
            date: Date to set as current
        """
        self.current_date = GameDate(
            date.year,
            date.month,
            date.day,
            date.hour
        )
    
    def __str__(self) -> str:
        return f"GameClock(current={self.current_date}, elapsed={self.elapsed_days()} days)"
    
    def __repr__(self) -> str:
        return f"GameClock(start_date={self.start_date}, current_date={self.current_date})"


# Common historical dates
HISTORICAL_DATES = {
    "game_start": GameDate(1936, 1, 1),
    "spanish_civil_war": GameDate(1936, 7, 17),
    "anschluss": GameDate(1938, 3, 12),
    "munich_agreement": GameDate(1938, 9, 30),
    "war_start": GameDate(1939, 9, 1),
    "fall_of_france": GameDate(1940, 6, 22),
    "barbarossa": GameDate(1941, 6, 22),
    "pearl_harbor": GameDate(1941, 12, 7),
    "stalingrad": GameDate(1942, 8, 23),
    "d_day": GameDate(1944, 6, 6),
    "war_end_europe": GameDate(1945, 5, 8),
    "war_end_pacific": GameDate(1945, 9, 2),
}
