"""Patch for SQLAlchemy compatibility with Python 3.13"""
import sys
import types
from typing import TypeVar, Generic

_T_co = TypeVar('_T_co', covariant=True)

class TypingOnly:
    """Base class for typing-only operations"""
    pass

class SQLCoreOperations(Generic[_T_co], TypingOnly):
    """Patched SQLCoreOperations class"""
    def __init__(self):
        # Remove problematic attributes if they exist
        if hasattr(self, '__static_attributes__'):
            delattr(self, '__static_attributes__')
        if hasattr(self, '__firstlineno__'):
            delattr(self, '__firstlineno__')

# Apply the patch
import sqlalchemy.sql.elements
sqlalchemy.sql.elements.SQLCoreOperations = SQLCoreOperations 