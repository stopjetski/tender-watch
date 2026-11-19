from tender_watch import notion_sync
from tests.test_store_report import notice


class FakeNotion:
    def __init__(self, existing_columns=None):
        self.calls = []
        self.columns = existing_columns or {"Name": {"type": "title"}}
        self.next_page = 0

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            return {"properties": self.columns}
        if method == "POST":
            self.next_page += 1
            return {"id": f"page-{self.next_page}"}
        return {}


def stored(number="1", **changes):
    record = notice(number, **changes)
    record.update(status="open", first_seen_at="2026-11-19T22:00:00Z")
    return record


def test_missing_columns_are_added_and_the_title_column_is_found():
    client = FakeNotion()
    assert notion_sync.ensure_columns(client, "db") == "Name"
    added = client.calls[1][2]["properties"]
    assert {"Checked", "Problem", "Notice ID", "Deadline"} <= set(added)
    assert added["Checked"] == {"checkbox": {}}


def test_the_reviewers_columns_are_never_written():
    properties = notion_sync.properties_for(stored(), "Name")
    assert not set(notion_sync.REVIEWER_COLUMNS) & set(properties)


def test_a_notice_becomes_a_row():
    properties = notion_sync.properties_for(stored(country_name="Congo, Democratic Republic of"), "Name")
    assert properties["Name"]["title"][0]["text"]["content"] == "Supply of pumps"
    assert properties["Deadline"] == {"date": {"start": "2026-11-20"}}
    assert properties["Deadline time (local)"]["rich_text"][0]["text"]["content"] == "10:00"
    assert properties["Country"]["select"]["name"] == "Congo · Democratic Republic of"
    assert properties["Missing fields"]["multi_select"] == [{"name": "document_urls"}]


def test_only_new_and_changed_notices_are_sent():
    client, state = FakeNotion(), {}
    notices = {"worldbank:OP1": stored("1"), "worldbank:OP2": stored("2")}
    first = notion_sync.sync(client, "db", notices, state)
    assert (first["created"], first["updated"]) == (2, 0)
    second = notion_sync.sync(client, "db", notices, state)
    assert (second["created"], second["updated"], second["unchanged"]) == (0, 0, 2)
    notices["worldbank:OP1"] = stored("1", deadline="2026-12-05T10:00:00")
    third = notion_sync.sync(client, "db", notices, state)
    assert (third["created"], third["updated"], third["unchanged"]) == (0, 1, 1)
    assert client.calls[-1][:2] == ("PATCH", "/pages/page-1")


def test_without_a_token_the_copy_is_skipped_quietly(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    assert notion_sync.main(tmp_path) == 0
    assert "not set up" in capsys.readouterr().out
