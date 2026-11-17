from app import main  # noqa: F401  (routes register on import)


def test_robots_points_at_the_sitemap_on_the_request_host(client):
    body = client.get("/robots.txt").text
    assert "Sitemap: http://testserver/sitemap.xml" in body
    assert "Allow: /" in body


def test_sitemap_lists_the_home_page(client):
    r = client.get("/sitemap.xml")
    assert r.headers["content-type"].startswith("application/xml")
    assert "<loc>http://testserver/</loc>" in r.text


def test_public_url_wins_over_the_request_host(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://policylens.example/")
    assert "<loc>https://policylens.example/</loc>" in client.get("/sitemap.xml").text
    assert "Sitemap: https://policylens.example/sitemap.xml" in client.get("/robots.txt").text
