from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.main import create_app
from app.models.company import Company
from app.models.federation import Federation
from app.models.legal_entity import LegalEntity
from app.repositories.legal_entities import LegalEntityRepository
from app.schemas.legal_entity import (
    LegalEntityCreateRequest,
    LegalEntityResponse,
    LegalEntityUpdateRequest,
)
from app.services.legal_entities import LegalEntityService
from tests.factories import create_user

LEGAL_ENTITIES_PATH = "/legal_entities"


@pytest_asyncio.fixture
async def legal_entity_company(db_session: AsyncSession) -> Company:
    owner = await create_user(db_session, email="legal-entity-owner@example.com")
    federation = Federation(name="Legal entity federation", created_by_id=owner.id)
    db_session.add(federation)
    await db_session.flush()

    company = Company(
        name="Legal entity company", federation_id=federation.id, created_by_id=owner.id
    )
    db_session.add(company)
    await db_session.commit()
    return company


@pytest_asyncio.fixture
async def other_company(
    db_session: AsyncSession, legal_entity_company: Company
) -> Company:
    company = Company(
        name="Other company",
        federation_id=legal_entity_company.federation_id,
        created_by_id=legal_entity_company.created_by_id,
    )
    db_session.add(company)
    await db_session.commit()
    return company


@pytest_asyncio.fixture
async def legal_entity_client(
    legal_entity_company: Company, test_engine: AsyncEngine, test_settings: Settings
) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = get_test_session
    app.dependency_overrides[get_app_settings] = lambda: test_settings
    token = create_access_token(
        subject=str(legal_entity_company.created_by_id), settings=test_settings
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=f"http://testserver{test_settings.api_prefix}",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


async def test_legal_entity_repository_creates_and_filters_by_company(
    db_session: AsyncSession, legal_entity_company: Company, other_company: Company
) -> None:
    company_id = legal_entity_company.id
    repository = LegalEntityRepository(db_session)
    created = await repository.create(LegalEntity(company_id=company_id, name="Alpha"))
    await repository.create(LegalEntity(company_id=other_company.id, name="Beta"))
    await db_session.commit()
    db_session.expunge_all()

    loaded = await repository.get(created.id)
    assert loaded is not None
    assert loaded.name == "Alpha"
    assert loaded.company_id == company_id
    assert loaded.created_at is not None
    assert loaded.updated_at is not None

    matching = await repository.find_by_name("Alpha", company_id)
    assert matching is not None and matching.id == created.id
    assert await repository.find_by_name("Alpha", other_company.id) is None
    assert [item.id for item in await repository.list_by_company(company_id)] == [
        created.id
    ]

    await db_session.refresh(loaded, attribute_names=["company"])
    assert loaded.company.id == company_id
    await db_session.refresh(loaded.company, attribute_names=["legal_entities"])
    assert [item.id for item in loaded.company.legal_entities] == [created.id]


async def test_legal_entity_repository_skips_soft_deleted_records(
    db_session: AsyncSession, legal_entity_company: Company
) -> None:
    company_id = legal_entity_company.id
    repository = LegalEntityRepository(db_session)
    active = await repository.create(LegalEntity(company_id=company_id, name="Active"))
    deleted = await repository.create(
        LegalEntity(
            company_id=company_id, name="Archived", deleted_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    assert await repository.get(deleted.id) is None
    assert await repository.get(uuid4()) is None
    assert await repository.find_by_name("Archived", company_id) is None
    assert [item.id for item in await repository.list_by_company(company_id)] == [
        active.id
    ]


async def test_legal_entity_service_creates_updates_and_lists(
    db_session: AsyncSession, legal_entity_company: Company
) -> None:
    company_id = legal_entity_company.id
    service = LegalEntityService(db_session)

    created = await service.create("Original", company_id)
    assert (await service.get(created.id)).name == "Original"
    assert [item.id for item in await service.list_by_company(company_id)] == [
        created.id
    ]

    updated = await service.update("Renamed", created.id)
    db_session.expunge_all()
    assert updated.id == created.id
    assert (await service.get(created.id)).name == "Renamed"
    assert (await service.update("Renamed", created.id)).name == "Renamed"


async def test_legal_entity_service_rejects_duplicate_names(
    db_session: AsyncSession, legal_entity_company: Company, other_company: Company
) -> None:
    company_id = legal_entity_company.id
    other_company_id = other_company.id
    service = LegalEntityService(db_session)
    await service.create("Taken", company_id)
    other = await service.create("Other", company_id)
    other_id = other.id

    with pytest.raises(ConflictError):
        await service.create("Taken", company_id)
    await db_session.rollback()

    with pytest.raises(ConflictError):
        await service.update("Taken", other_id)
    await db_session.rollback()

    assert (await service.get(other_id)).name == "Other"
    assert {item.name for item in await service.list_by_company(company_id)} == {
        "Taken",
        "Other",
    }
    same_name = await service.create("Taken", other_company_id)
    assert same_name.company_id == other_company_id


async def test_legal_entity_service_requires_an_active_company(
    db_session: AsyncSession, legal_entity_company: Company
) -> None:
    service = LegalEntityService(db_session)
    with pytest.raises(NotFoundError):
        await service.create("Entity", uuid4())

    legal_entity_company.deleted_at = datetime.now(UTC)
    await db_session.commit()
    with pytest.raises(NotFoundError):
        await service.create("Entity", legal_entity_company.id)


async def test_legal_entity_service_hides_deleted_entities_and_reuses_their_names(
    db_session: AsyncSession, legal_entity_company: Company
) -> None:
    service = LegalEntityService(db_session)
    company_id = legal_entity_company.id
    deleted = await service.create("Reusable name", company_id)
    deleted.deleted_at = datetime.now(UTC)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await service.get(deleted.id)
    with pytest.raises(NotFoundError):
        await service.update("Changed", deleted.id)

    replacement = await service.create("Reusable name", company_id)
    assert replacement.id != deleted.id
    assert [item.id for item in await service.list_by_company(company_id)] == [
        replacement.id
    ]


async def test_legal_entity_concurrent_create_and_rename_preserve_unique_names(
    db_session: AsyncSession, legal_entity_company: Company, test_engine: AsyncEngine
) -> None:
    company_id = legal_entity_company.id
    service = LegalEntityService(db_session)
    existing = await service.create("Existing", company_id)
    existing_id = existing.id
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_factory() as create_session, session_factory() as rename_session:
        results = await asyncio.wait_for(
            asyncio.gather(
                LegalEntityService(create_session).create("Same name", company_id),
                LegalEntityService(rename_session).update("Same name", existing_id),
                return_exceptions=True,
            ),
            timeout=10,
        )

    assert sum(isinstance(result, LegalEntity) for result in results) == 1, results
    assert sum(isinstance(result, ConflictError) for result in results) == 1, results
    entities = await service.list_by_company(company_id)
    assert sum(entity.name == "Same name" for entity in entities) == 1


@pytest.mark.parametrize("name", ["A", "B" * 100])
def test_legal_entity_request_schemas_accept_name_boundaries(name: str) -> None:
    company_id = uuid4()
    assert LegalEntityCreateRequest(company_id=company_id, name=name).name == name
    assert LegalEntityUpdateRequest(name=name).model_dump() == {"name": name}


def test_legal_entity_response_schema_reads_orm_attributes() -> None:
    timestamp = datetime.now(UTC)
    entity = LegalEntity(
        id=uuid4(),
        company_id=uuid4(),
        name="Entity",
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = LegalEntityResponse.model_validate(entity)

    assert response.model_dump() == {
        "id": entity.id,
        "company_id": entity.company_id,
        "name": "Entity",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


async def test_legal_entity_openapi_documents_all_routes(
    legal_entity_client: AsyncClient, test_settings: Settings
) -> None:
    docs = await legal_entity_client.get("http://testserver/docs")
    assert docs.status_code == 200
    spec = await legal_entity_client.get("http://testserver/openapi.json")
    assert spec.status_code == 200

    paths = spec.json()["paths"]
    path = f"{test_settings.api_prefix}{LEGAL_ENTITIES_PATH}"
    assert {"get", "post", "patch"} <= paths[path].keys()
    assert "get" in paths[f"{path}/{{legal_entity_id}}"]


async def test_legal_entity_http_creates_reads_lists_and_updates(
    legal_entity_client: AsyncClient, legal_entity_company: Company
) -> None:
    company_id = str(legal_entity_company.id)
    created = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": company_id, "name": "Original"}
    )
    assert created.status_code == 200
    entity = created.json()
    assert entity["company_id"] == company_id
    assert entity["name"] == "Original"
    entity_path = f"{LEGAL_ENTITIES_PATH}/{entity['id']}"

    loaded = await legal_entity_client.get(entity_path)
    assert loaded.status_code == 200
    assert loaded.json() == entity

    listing = await legal_entity_client.get(
        LEGAL_ENTITIES_PATH, params={"company_id": company_id}
    )
    assert listing.status_code == 200
    assert listing.json() == [entity]

    updated = await legal_entity_client.patch(
        LEGAL_ENTITIES_PATH,
        params={"legal_entity_id": entity["id"]},
        json={"name": "Renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == entity["id"]
    assert updated.json()["name"] == "Renamed"
    loaded = await legal_entity_client.get(entity_path)
    assert loaded.status_code == 200
    assert loaded.json() == updated.json()


async def test_legal_entity_http_returns_404_for_missing_company_or_entity(
    legal_entity_client: AsyncClient,
) -> None:
    missing_id = str(uuid4())
    created = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": missing_id, "name": "Entity"}
    )
    loaded = await legal_entity_client.get(f"{LEGAL_ENTITIES_PATH}/{missing_id}")
    updated = await legal_entity_client.patch(
        LEGAL_ENTITIES_PATH,
        params={"legal_entity_id": missing_id},
        json={"name": "New"},
    )
    assert [response.status_code for response in (created, loaded, updated)] == [
        404
    ] * 3


async def test_legal_entity_http_rejects_duplicates_and_keeps_original_name(
    legal_entity_client: AsyncClient, legal_entity_company: Company
) -> None:
    company_id = str(legal_entity_company.id)
    taken = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": company_id, "name": "Taken"}
    )
    other = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": company_id, "name": "Other"}
    )
    assert taken.status_code == other.status_code == 200
    other_id = other.json()["id"]

    duplicate = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": company_id, "name": "Taken"}
    )
    assert duplicate.status_code == 409
    renamed = await legal_entity_client.patch(
        LEGAL_ENTITIES_PATH,
        params={"legal_entity_id": other_id},
        json={"name": "Taken"},
    )
    assert renamed.status_code == 409
    loaded = await legal_entity_client.get(f"{LEGAL_ENTITIES_PATH}/{other_id}")
    assert loaded.status_code == 200
    assert loaded.json()["name"] == "Other"


@pytest.mark.parametrize("name", ["", "A" * 101])
async def test_legal_entity_http_validates_names_on_create_and_update(
    name: str, legal_entity_client: AsyncClient, legal_entity_company: Company
) -> None:
    company_id = str(legal_entity_company.id)
    created = await legal_entity_client.post(
        LEGAL_ENTITIES_PATH, json={"company_id": company_id, "name": name}
    )
    updated = await legal_entity_client.patch(
        LEGAL_ENTITIES_PATH,
        params={"legal_entity_id": str(uuid4())},
        json={"name": name},
    )
    for response in (created, updated):
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "name"]


async def test_legal_entity_http_requires_authentication(
    legal_entity_client: AsyncClient, legal_entity_company: Company
) -> None:
    del legal_entity_client.headers["Authorization"]
    response = await legal_entity_client.get(
        LEGAL_ENTITIES_PATH, params={"company_id": str(legal_entity_company.id)}
    )
    assert response.status_code == 401


async def test_legal_entity_http_rejects_invalid_id(
    legal_entity_client: AsyncClient,
) -> None:
    response = await legal_entity_client.get(f"{LEGAL_ENTITIES_PATH}/invalid-uuid")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "legal_entity_id"]
