import pytest
from app.services.matching import calculate_rank, calculate_match, parse_need_text

class DummyCandidate:
    def __init__(self, **kwargs):
        self.theta_norm = 0.5
        self.grade = 2
        self.is_confirmed = True
        self.skills = []
        self.fresh_days = 10
        self.context_score = 1.0
        self.avail_score = 1.0
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_grade_qualifier():
    c_unconfirmed = DummyCandidate(grade=2, is_confirmed=False)
    c_confirmed = DummyCandidate(grade=2, is_confirmed=True)
    need = {
        "grade_min": 2,
        "grade_max": 3,
        "must_have_skills": []
    }
    match_un = calculate_match(c_unconfirmed, need)
    match_co = calculate_match(c_confirmed, need)
    
    # confirmed candidate gets higher score
    assert match_co["score"] > match_un["score"]
    
    # ensure explanation output reflects the new formula prioritization
    assert match_co["explain"]["grade_match"] > match_un["explain"]["grade_match"]

def test_rank_no_fsp():
    c = DummyCandidate(theta_norm=0.8)
    rank_with_fsp = calculate_rank(c, fsp_index=1.0, fresh_days=10)
    rank_no_fsp = calculate_rank(c, fsp_index=0.0, fresh_days=10)
    assert rank_with_fsp > rank_no_fsp

def test_match_no_fsp_variance():
    c = DummyCandidate(skills=["python", "postgresql"], grade=2, is_confirmed=True)
    need = {
        "grade_min": 2,
        "grade_max": 3,
        "must_have_skills": ["python", "postgresql"]
    }
    # Pool has 0 variance (e.g. no one has FSP)
    match_zero_var = calculate_match(c, need, fsp_pool_percentile=0.0, fsp_pool_variance_zero=True)
    # Pool has variance, this guy has 0
    match_var_zero_fsp = calculate_match(c, need, fsp_pool_percentile=0.0, fsp_pool_variance_zero=False)
    
    # Weight should be redistributed to grade and skills, so overall score should be higher or equal depending on skills
    # Let's just check it doesn't penalize.
    assert match_zero_var["score"] > match_var_zero_fsp["score"]

def test_must_have_penalty():
    c1 = DummyCandidate(skills=["python", "postgresql", "docker"]) # missing kubernetes
    c2 = DummyCandidate(skills=["python", "postgresql"]) # missing docker, kubernetes
    
    need = {
        "must_have_skills": ["python", "postgresql", "docker", "kubernetes"]
    }
    
    m1 = calculate_match(c1, need)
    m2 = calculate_match(c2, need)
    
    assert m1["score"] > m2["score"]

def test_parsing():
    # Фразы из брифа:
    cases = [
        ("нужен бэкендер на питоне, постгрес, докер и кубер", ["python", "postgresql", "docker", "kubernetes"]),
        ("фронтендер с реактом и тайпскриптом", ["react", "typescript"]),
        ("дата-инженер: спарк, хадуп, эйрфлоу", ["spark", "hadoop", "airflow"]),
        ("тестировщик: селениум, питон, джира", ["selenium", "python", "jira"]),
        ("ищем Go-разработчика с опытом в Kafka и RabbitMQ", ["go", "kafka", "rabbitmq"]),
        ("нужен ML-инженер, знает PyTorch и pandas", ["pytorch", "pandas"]),
        ("бэкенд на Python + PostgreSQL, Docker, Redis", ["python", "postgresql", "docker", "redis"]),
        ("ищем сеньора: Kubernetes, Terraform, CI/CD", ["kubernetes", "terraform", "ci-cd"])
    ]
    
    for phrase, expected in cases:
        parsed = parse_need_text(phrase)
        found = parsed["must_have_skills"]
        for exp in expected:
            assert exp in found, f"Missing {exp} in {found} for '{phrase}'"
