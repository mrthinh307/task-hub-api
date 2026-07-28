from app.repositories.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, repo: WorkspaceRepository):
        self.repo = repo
