def __init__(self, db_path: str) -> None:
    self._db_path = db_path   # ← ADD THIS
    self._db = Database(db_path)
    ...
