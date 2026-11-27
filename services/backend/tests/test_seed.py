from sqlalchemy import func, select

from peak.models import Skill
from peak.seed import seed_skills
from peak.taxonomy import OFFICIAL_SKILLS


def test_seed_is_idempotent_and_complete(db):
    first = seed_skills(db)
    assert first == sum(len(v) for v in OFFICIAL_SKILLS.values()) + 12
    assert seed_skills(db) == 0
    assert db.scalar(select(func.count()).select_from(Skill)) == first


def test_micro_skills_have_parents_and_cues(db):
    seed_skills(db)
    micro = db.scalars(select(Skill).where(Skill.micro_skill.is_not(None))).all()
    assert micro and all(m.parent_id and m.cue for m in micro)
    ids = set(db.scalars(select(Skill.id)))
    assert all(m.parent_id in ids for m in micro)


def test_official_skill_count_gives_87_cells_with_three_difficulties():
    assert sum(len(v) for v in OFFICIAL_SKILLS.values()) * 3 == 87
