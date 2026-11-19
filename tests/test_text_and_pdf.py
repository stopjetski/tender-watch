from tender_watch.pdftext import PdfCache, extract_text
from tender_watch.textfields import find_deadline


def test_french_deadline_phrase():
    text = "Les offres doivent être déposées au plus tard le 15 décembre 2026 à 10 heures. Publié le 1er novembre 2026."
    assert find_deadline(text) == ("2026-12-15", "au plus tard")


def test_english_deadline_phrase_beats_an_earlier_date():
    text = "Issued on 29 October 2026. Bids must be delivered to the address below on or before 26 November 2026 at 12:00."
    assert find_deadline(text)[0] == "2026-11-26"


def test_portuguese_deadline_phrase():
    assert find_deadline("As propostas devem ser entregues até às 15h00 do dia 3 de dezembro de 2026.")[0] == "2026-12-03"


def test_no_phrase_means_no_deadline_rather_than_a_guess():
    assert find_deadline("Signed on 3 March 2026 in Abidjan.") == (None, None)
    assert find_deadline("") == (None, None)


def test_french_pdf_text_keeps_its_accents(fixtures):
    # A made-up sample in the style of a bank notice, not a real document.
    text, notes = extract_text((fixtures / "pdf" / "synthetic_avis_fr.pdf").read_bytes())
    assert notes == []
    assert "République du Sénégal" in text
    assert "électrification" in text
    assert find_deadline(text)[0] == "2026-12-15"


class OneFileSession:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def get(self, url):
        self.calls += 1

        class Reply:
            content = self.data

        return Reply()


def test_each_pdf_is_downloaded_once(fixtures, tmp_path):
    session = OneFileSession((fixtures / "pdf" / "synthetic_avis_fr.pdf").read_bytes())
    cache = PdfCache(session, tmp_path / "pdf")
    first, _ = cache.text("https://example.org/a.pdf")
    second, _ = PdfCache(session, tmp_path / "pdf").text("https://example.org/a.pdf")
    assert first == second and "Sénégal" in first
    assert session.calls == 1


def test_a_broken_pdf_is_noted_not_fatal(tmp_path):
    cache = PdfCache(OneFileSession(b"this is not a pdf"), tmp_path / "pdf")
    text, notes = cache.text("https://example.org/broken.pdf")
    assert text == "" and "could not be read" in notes[0]
