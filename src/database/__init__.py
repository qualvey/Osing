from .sqlite import ProxyUserDB
from Settings import settings
config = settings.config
ctx = settings.ctx
db = ProxyUserDB(db_path=ctx.db_path)

__all__ = [
    'ProxyUserDB',
    'db'
]
