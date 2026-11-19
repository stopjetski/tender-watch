import pytest

from tender_watch.http import USER_AGENT, Blocked, FetchFailed, PoliteSession

ROBOTS = "User-agent: *\nDisallow: /private/\n"
CHALLENGE = "<html><title>Just a moment...</title>Enable JavaScript and cookies to continue</html>"


def make(fake_requests, fake_clock, answer):
    http = fake_requests(answer)
    return PoliteSession(session=http, sleep=fake_clock.sleep, clock=fake_clock.clock), http


def test_the_bot_names_itself_and_the_repo(fake_requests, fake_clock, fake_response):
    session, http = make(fake_requests, fake_clock, lambda url, kw: fake_response(text=ROBOTS))
    session.get("https://bank.example/notices")
    assert http.headers["User-Agent"] == USER_AGENT
    assert "tender-watch" in USER_AGENT and "github.com/stopjetski/tender-watch" in USER_AGENT


def test_never_more_than_one_request_a_second_per_site(fake_requests, fake_clock, fake_response):
    session, http = make(fake_requests, fake_clock, lambda url, kw: fake_response(text=ROBOTS))
    for page in range(3):
        session.get(f"https://bank.example/notices?page={page}")
    assert len(http.calls) == 4  # robots.txt once, then three pages
    assert fake_clock.sleeps == [1.0, 1.0, 1.0]


def test_robots_rules_are_obeyed(fake_requests, fake_clock, fake_response):
    session, http = make(fake_requests, fake_clock, lambda url, kw: fake_response(text=ROBOTS))
    with pytest.raises(Blocked):
        session.get("https://bank.example/private/file")
    assert [url for url, _ in http.calls] == ["https://bank.example/robots.txt"]


def test_no_robots_file_means_nothing_is_disallowed(fake_requests, fake_clock, fake_response):
    def answer(url, kw):
        return fake_response(status_code=404) if url.endswith("robots.txt") else fake_response(text="ok")

    session, _ = make(fake_requests, fake_clock, answer)
    assert session.get("https://bank.example/notices").text == "ok"


def test_a_browser_challenge_is_a_block_and_is_not_retried(fake_requests, fake_clock, fake_response):
    challenge = lambda url, kw: fake_response(status_code=403, text=CHALLENGE, headers={"cf-mitigated": "challenge"})  # noqa: E731
    session, http = make(fake_requests, fake_clock, challenge)
    with pytest.raises(Blocked):
        session.get("https://bank.example/notices")
    assert len(http.calls) == 1


def test_a_busy_server_is_retried_with_growing_waits(fake_requests, fake_clock, fake_response):
    replies = [fake_response(status_code=404), fake_response(status_code=503), fake_response(status_code=502), fake_response(text="ok")]
    session, http = make(fake_requests, fake_clock, replies)
    assert session.get("https://bank.example/notices").text == "ok"
    assert len(http.calls) == 4
    assert 2.0 in fake_clock.sleeps and 4.0 in fake_clock.sleeps


def test_it_gives_up_after_the_last_retry(fake_requests, fake_clock, fake_response):
    def answer(url, kw):
        return fake_response(status_code=404) if url.endswith("robots.txt") else fake_response(status_code=500)

    session, http = make(fake_requests, fake_clock, answer)
    with pytest.raises(FetchFailed):
        session.get("https://bank.example/notices")
    assert len(http.calls) == 1 + 5
