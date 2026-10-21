"""Which organisation a request acts for (PLAN-014 D5).

Every table in the ``app`` schema carries ``org_id``. Until accounts exist (PLAN-014 C2)
there is one organisation, created by migration 007, and every request acts for it. When
accounts arrive, this function reads the signed-in user's organisation instead, and
nothing that depends on it has to change.
"""

from __future__ import annotations

from uuid import UUID

DEFAULT_ORG = UUID("00000000-0000-0000-0000-000000000001")


def current_org() -> UUID:
    return DEFAULT_ORG
