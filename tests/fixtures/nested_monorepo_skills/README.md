# nested_monorepo_skills (fixture)

A monorepo whose skills live two levels deep, under a named group directory
that is NOT itself a skill:

```
nested_monorepo_skills/
└── aj-workflows/        # group dir, no SKILL.md of its own
    ├── aj-flow/SKILL.md
    └── aj-issue/SKILL.md
```

Mirrors AJ's `personal_skills/aj-workflows/<skill>` layout. Used to exercise
multi-segment skill_path handling end-to-end (add → install → doctor repair).
Not a real skill.
