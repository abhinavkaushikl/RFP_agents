"""Who may see which runs."""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AccessScope:
    """The viewer of a request.

    `restricted` viewers (signed-in members) only see runs they own. Everyone else is unrestricted:
    admins, API-key scripts, and local use with auth switched off.
    """

    owner_id: uuid.UUID | None = None
    restricted: bool = False

    def allows(self, run_owner_id: uuid.UUID | None) -> bool:
        return not self.restricted or (run_owner_id is not None and run_owner_id == self.owner_id)


UNRESTRICTED = AccessScope()
