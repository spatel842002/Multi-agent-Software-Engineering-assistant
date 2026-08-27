"""Import every model module so `Base.metadata` is fully populated for Alembic
autogenerate and for `create_all()` in tests.
"""

from app.models.conversation import Citation, Conversation, Message  # noqa: F401
from app.models.misc import EvalRun, IdempotencyKey  # noqa: F401
from app.models.patch import ApprovalEvent, PatchProposal  # noqa: F401
from app.models.repository import Chunk, IngestedFile, Repository, Symbol  # noqa: F401
from app.models.user import RefreshToken, User  # noqa: F401
