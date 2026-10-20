"""A person's library of existing solutions, and who may see or change what.

Members see and change only their own. Admins can see everyone's and delete anyone's, but only
edit their own, so an admin can't quietly rewrite someone else's content.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access import AccessScope
from app.core.errors import AppError, NotFoundError
from app.db.models import ExistingSolution, User


class SolutionConflictError(AppError):
    status_code = 409
    code = "conflict"


class SolutionForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


class SolutionStore:
    def __init__(self, db: Session, scope: AccessScope) -> None:
        self.db = db
        self.scope = scope

    # ── helpers ───────────────────────────────────────────────────────
    def _owner_for_writes(self) -> uuid.UUID:
        if self.scope.owner_id is None:
            raise SolutionForbiddenError("Sign in to manage your solutions.")
        return self.scope.owner_id

    def _can_see(self, row: ExistingSolution) -> bool:
        return self.scope.is_admin or not self.scope.restricted or row.owner_id == self.scope.owner_id

    def _get_visible(self, solution_id: str) -> ExistingSolution:
        sid = _uuid(solution_id)
        row = self.db.get(ExistingSolution, sid) if sid else None
        if row is None or not self._can_see(row):
            raise NotFoundError("Solution not found.")  # same answer for "doesn't exist" and "isn't yours"
        return row

    def _present(self, row: ExistingSolution, owners: dict[uuid.UUID, str] | None = None) -> dict[str, Any]:
        data = {
            "id": str(row.id),
            "name": row.name,
            "category": row.category,
            "status": row.status,
            "description": row.description,
            "capabilities": list(row.capabilities or []),
            "url": row.url,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "mine": row.owner_id == self.scope.owner_id,
        }
        if self.scope.is_admin and owners is not None:
            data["owner_email"] = owners.get(row.owner_id, "")
        return data

    # ── reads ─────────────────────────────────────────────────────────
    def list(self, *, query: str | None = None, everyone: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        stmt = select(ExistingSolution).order_by(ExistingSolution.updated_at.desc()).limit(max(1, min(limit, 500)))
        if not (self.scope.is_admin and everyone):
            stmt = stmt.where(ExistingSolution.owner_id == self._owner_for_writes())
        if query and query.strip():
            like = f"%{query.strip()}%"
            stmt = stmt.where(or_(
                ExistingSolution.name.ilike(like),
                ExistingSolution.category.ilike(like),
                ExistingSolution.description.ilike(like),
            ))
        rows = list(self.db.execute(stmt).scalars())
        owners: dict[uuid.UUID, str] = {}
        if self.scope.is_admin and rows:
            ids = {r.owner_id for r in rows}
            owners = {u.id: u.email for u in self.db.execute(select(User).where(User.id.in_(ids))).scalars()}
        return [self._present(r, owners) for r in rows]

    def get(self, solution_id: str) -> dict[str, Any]:
        row = self._get_visible(solution_id)
        owners = {row.owner_id: self.db.get(User, row.owner_id).email} if self.scope.is_admin else None
        return self._present(row, owners)

    # ── writes ────────────────────────────────────────────────────────
    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        row = ExistingSolution(id=uuid.uuid4(), owner_id=self._owner_for_writes(), **fields)
        self.db.add(row)
        self._commit()
        return self._present(row)

    def update(self, solution_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self._get_visible(solution_id)
        if row.owner_id != self.scope.owner_id:
            raise SolutionForbiddenError("You can view this solution but only its owner can edit it.")
        for key, value in fields.items():
            setattr(row, key, value)
        self._commit()
        return self._present(row)

    def delete(self, solution_id: str) -> None:
        row = self._get_visible(solution_id)  # members: own only; admins: anyone's
        self.db.delete(row)
        self.db.commit()

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise SolutionConflictError("You already have a solution with that name.") from None
