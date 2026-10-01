from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    )
    return resp.json()


def test_paste_story(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/stories/paste",
        json={"title": "Petty Cash Retirement", "text": "Check that the limit is 150000."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Petty Cash Retirement"
    assert body["source"] == "paste"

    detail = user_client.get(f"/api/v1/stories/{body['id']}")
    assert detail.status_code == 200
    assert "150000" in detail.json()["extracted_text"]


def test_upload_story_txt(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/stories/upload",
        files={
            "file": ("story.txt", b"Users must log in before requesting petty cash.", "text/plain")
        },
    )
    assert resp.status_code == 201, resp.text
    assert "log in" in resp.json()["title"] or resp.json()["title"] == "story.txt"


def test_upload_unsupported_file_type_rejected(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/stories/upload",
        files={"file": ("story.png", b"\x89PNG\r\n", "image/png")},
    )
    assert resp.status_code == 400


def test_list_stories_for_project(user_client: TestClient) -> None:
    project = _create_project(user_client)
    user_client.post(
        f"/api/v1/projects/{project['id']}/stories/paste",
        json={"title": "Story A", "text": "Some text."},
    )
    user_client.post(
        f"/api/v1/projects/{project['id']}/stories/paste",
        json={"title": "Story B", "text": "Some text."},
    )
    resp = user_client.get(f"/api/v1/projects/{project['id']}/stories")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_stories_require_project_access(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/stories/paste",
        json={"title": "x", "text": "y"},
    )
    assert resp.status_code == 401
