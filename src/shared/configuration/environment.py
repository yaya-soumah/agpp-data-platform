from enum import Enum

class Environment(Enum):
    """Enum representing different application environments."""
    
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"