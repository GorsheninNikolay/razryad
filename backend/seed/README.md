# Детерминированный seed

Запуск: `python3 seed/generate.py --seed 42 --check && python3 seed/seed.py` из `backend/`.

Демо-аккаунты (пароль `DemoRazryad42!`):
- `novice@razryad.demo` — кандидат, Intern, без ФСП
- `middle@razryad.demo` — кандидат, подтверждённый Middle,  ФСП
- `provisional@razryad.demo` — кандидат с неподтверждённой категорией
- `employer1@razryad.demo`, `employer2@razryad.demo` — работодатели

Фикстуры генерируются seed=42, проверка включает число сущностей, навыки из skills.json, валидные IRT a/b и 20 якорей.
