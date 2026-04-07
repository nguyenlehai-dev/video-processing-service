class TestAuth:
    """Test authentication endpoints."""

    def test_register(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass123",
            "full_name": "Test User",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"

    def test_login(self, client):
        # Register first
        client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "testpass123",
        })
        # Login
        response = client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "testpass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "testpass123",
        })
        response = client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    def test_me(self, client):
        # Register and login
        client.post("/api/v1/auth/register", json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "testpass123",
        })
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "me@example.com",
            "password": "testpass123",
        })
        token = login_resp.json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()
