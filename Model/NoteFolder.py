class NoteFolder:
    def __init__(self, uuid: str, name: str):
        self.uuid: str = uuid
        self.name: str = name.strip()
