from app.repositories.label_repository import LabelRepository


class LabelService:
    def __init__(self, repo: LabelRepository):
        self.repo = repo
