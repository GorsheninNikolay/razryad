"""Pytest configuration and fixtures"""
import os
import tempfile
import json
from pathlib import Path

# ЗАЩИТА ОБЩЕЙ ДЕМО-БАЗЫ.
#
# Переменную окружения надо выставить ДО импорта app.core.db: настройки читаются
# при создании объекта settings, и от них зависит адрес движка. Без этого любой
# тест, обратившийся к `engine` из app.core.db, работает с общей базой
# `backend/razryad.db` — и вызов `Base.metadata.drop_all(bind=engine)` сносит все
# 47 таблиц демо-данных. Именно это происходило при каждом прогоне `make test`.
#
# Теперь даже неаккуратно написанный тест физически не может дотянуться до
# демо-базы: движок приложения указывает на временный файл.
_TEST_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="razryad-tests-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def taxonomy_data():
    """Load taxonomy.json - single source of truth for reference data"""
    taxonomy_path = Path(__file__).parent.parent.parent / "content" / "taxonomy.json"
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_engine(taxonomy_data):
    """Create test database engine with reference data populated.

    Uses an isolated in-memory StaticPool database so TestClient worker threads
    and fixtures share one connection without touching the demo database.
    Reference data is loaded from content/taxonomy.json.
    """
    from app.models.models import Grade, Specialization, Blueprint, BlueprintWeight, Competency, Item, ItemVersion
    import uuid
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    # IRT theta thresholds for each grade (from real database)
    theta_thresholds = {
        "intern": -3.0,
        "junior": -1.5,
        "middle": 0.0,
        "senior": 1.5,
        "lead": 2.5
    }
    
    try:
        # Add grades
        for grade_data in taxonomy_data.get("grades", []):
            grade = Grade(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"grade-{grade_data['id']}"),
                code=grade_data["id"],
                name=grade_data["name"],
                level=grade_data["order"] - 1,  # Convert 1-5 to 0-4
                theta_threshold=theta_thresholds.get(grade_data["id"], 0.0)
            )
            db.add(grade)
        
        # Add specializations
        for spec_data in taxonomy_data.get("specializations", []):
            # competency_blueprint — NOT NULL, а без него падал весь сид справочника
            # и вместе с ним 44 теста (IntegrityError: NOT NULL constraint failed).
            # Веса берём из таксономии, а не заглушкой: от них зависит выбор заданий.
            spec = Specialization(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"spec-{spec_data['id']}"),
                code=spec_data["id"],
                name=spec_data["name"],
                description=spec_data.get("description", ""),
                competency_blueprint={
                    c["id"]: c["weight"] for c in spec_data.get("competencies", [])
                },
            )
            db.add(spec)
            db.flush()
            bp=Blueprint(name=f"{spec_data['id']} assessment",specialization_id=spec.id,is_active=True)
            db.add(bp);db.flush()
            for comp_data in spec_data.get('competencies', []):
                comp=Competency(code=f"{spec_data['id']}-{comp_data['id']}",
                                name=comp_data['name'],specialization_id=spec.id)
                db.add(comp);db.flush()
                db.add(BlueprintWeight(blueprint_id=bp.id,competency_id=comp.id,
                                       weight=comp_data['weight'],min_items=1))
        # Minimal calibrated bank for E2E: one MCQ per competency plus anchors.
        for spec_data in taxonomy_data.get('specializations', []):
            spec=db.query(Specialization).filter_by(code=spec_data['id']).one()
            for index, comp_data in enumerate(spec_data.get('competencies', [])):
                comp=db.query(Competency).filter_by(code=f"{spec_data['id']}-{comp_data['id']}").one()
                for variant in range(12):
                    item=Item(code=f"test-{spec_data['id']}-{comp_data['id']}-{variant}",specialization_id=spec.id,
                        competency_id=comp.id,item_type='mcq',status='active',discrimination=1.2,
                        difficulty=0.0,is_anchor=index<2 and variant==0,estimated_time_seconds=60)
                    db.add(item);db.flush()
                    db.add(ItemVersion(item_id=item.id,version=1,is_current=True,
                        content={'stem':f'Question {comp_data["id"]} variant {variant}','options':['A','B'],
                                 'correct_answer':'A'}))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
    
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with database override"""
    from fastapi.testclient import TestClient
    
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_candidate(client):
    """Create and authenticate a candidate - returns access token
    
    Uses unique email per test to avoid conflicts in test database
    """
    import uuid
    unique_email = f"candidate-{uuid.uuid4().hex[:8]}@test.com"
    
    # Register with valid password (min 8 chars)
    reg = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "testpass123",  # 11 chars - meets min_length requirement
        "role": "candidate"
    })
    
    if reg.status_code != 201:
        raise Exception(f"Registration failed: {reg.status_code} - {reg.json()}")
    
    # Extract confirmation token from response
    token = reg.json()["confirmation_link"].split("token=")[1]
    
    # Confirm email
    confirm = client.post("/api/v1/auth/confirm-email", json={"token": token})
    if confirm.status_code != 200:
        raise Exception(f"Email confirmation failed: {confirm.status_code} - {confirm.json()}")
    
    # Login
    login = client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "testpass123"
    })
    
    if login.status_code != 200:
        raise Exception(f"Login failed: {login.status_code} - {login.json()}")
    
    return login.json()["access_token"]


@pytest.fixture
def auth_employer(client):
    """Register, confirm and log in an employer using the isolated test client."""
    import uuid
    email = f"employer-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "role": "employer"
    })
    assert reg.status_code == 201, reg.json()
    token = reg.json()["confirmation_link"].split("token=")[1]
    confirm = client.post("/api/v1/auth/confirm-email", json={"token": token})
    assert confirm.status_code == 200, confirm.json()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.json()
    return login.json()["access_token"]
