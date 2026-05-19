"""Auth tests — bcrypt hashing + role gating arithmetic."""

from __future__ import annotations

from compass.auth import ROLE_RANK, User, can_decide, can_edit, hash_password, verify_password


def test_bcrypt_round_trip():
    h = hash_password("compass-demo")
    assert verify_password("compass-demo", h)
    assert not verify_password("wrong", h)


def test_role_rank_ordering():
    assert ROLE_RANK["READONLY"] < ROLE_RANK["PO"] < ROLE_RANK["PM"] < ROLE_RANK["COR"]


def test_can_edit():
    assert not can_edit(None)
    assert not can_edit(User(id=1, email="r", name="r", role="READONLY"))
    assert can_edit(User(id=2, email="p", name="p", role="PO"))
    assert can_edit(User(id=3, email="m", name="m", role="PM"))
    assert can_edit(User(id=4, email="c", name="c", role="COR"))


def test_can_decide():
    assert not can_decide(None)
    assert not can_decide(User(id=1, email="r", name="r", role="READONLY"))
    assert not can_decide(User(id=2, email="p", name="p", role="PO"))
    assert not can_decide(User(id=3, email="m", name="m", role="PM"))
    assert can_decide(User(id=4, email="c", name="c", role="COR"))
