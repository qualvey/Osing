from .sqlite import ProxyUserDB
from Settings import settings

db = ProxyUserDB(db_path=settings.sqlite_db_path)

__all__ = [
    'ProxyUserDB',
    'db'
]
