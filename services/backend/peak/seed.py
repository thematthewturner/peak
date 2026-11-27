"""Idempotent seeding of the skill tree: official skills plus Addison's micro-skills as children."""
from sqlalchemy import select

from .db import SessionLocal
from .models import Skill
from .taxonomy import DOMAINS, MICRO_SKILLS, OFFICIAL_SKILLS, skill_id


def seed_skills(db) -> int:
    existing = set(db.scalars(select(Skill.id)))
    added = 0
    for d in DOMAINS:
        for name in OFFICIAL_SKILLS[d.key]:
            sid = skill_id(d.key, name)
            if sid not in existing:
                db.add(Skill(id=sid, section=d.section.value, domain=d.key, skill=name, domain_weight=d.share))
                existing.add(sid)
                added += 1
    db.flush()
    domain_first = {d.key: skill_id(d.key, OFFICIAL_SKILLS[d.key][0]) for d in DOMAINS}
    for m in MICRO_SKILLS:
        sid = f"micro.{m.key}"
        if sid in existing:
            continue
        domain = m.domain or "algebra"
        parent = domain_first[domain]
        section = next(d.section.value for d in DOMAINS if d.key == domain)
        db.add(Skill(id=sid, section=section, domain=domain, skill=m.label, micro_skill=m.key,
                     parent_id=parent, domain_weight=0.0, cue=m.cue))
        added += 1
    db.commit()
    return added


def main():
    with SessionLocal() as db:
        print(f"seeded {seed_skills(db)} skills")


if __name__ == "__main__":
    main()
