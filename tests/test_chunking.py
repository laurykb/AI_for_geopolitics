"""Tests du chargement de corpus et du découpage en chunks."""

from rag.corpus import DEFAULT_CORPUS_DIR, chunk_documents, load_corpus
from rag.documents import SourceDoc


def _doc(text: str, did: str = "d1") -> SourceDoc:
    return SourceDoc(id=did, title="Titre", source="seed:x", text=text)


def test_short_document_is_single_chunk():
    chunks = chunk_documents([_doc("Court texte.")], max_chars=500)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.id == "d1#0"
    assert c.doc_id == "d1"
    assert c.title == "Titre"
    assert c.source == "seed:x"
    assert "seed:x" in c.citation


def test_long_document_is_split_under_max_chars():
    text = " ".join(f"mot{i}" for i in range(200))  # ~1200 chars
    chunks = chunk_documents([_doc(text)], max_chars=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)
    # ids séquentiels et provenance conservée
    assert [c.id for c in chunks] == [f"d1#{i}" for i in range(len(chunks))]


def test_chunks_overlap():
    text = " ".join(f"w{i}" for i in range(100))
    chunks = chunk_documents([_doc(text)], max_chars=100, overlap=40)
    assert len(chunks) >= 2
    # le dernier mot du chunk i réapparaît dans le chunk i+1 (recouvrement)
    first_words = set(chunks[0].text.split())
    second_words = chunks[1].text.split()
    assert any(w in first_words for w in second_words)


def test_load_seed_corpus_skips_eval_file():
    docs = load_corpus(DEFAULT_CORPUS_DIR)
    ids = {d.id for d in docs}
    assert "freedom-of-navigation" in ids
    assert "iran-sanctions" in ids
    assert len(docs) >= 6
    # le fichier d'évaluation n'est pas chargé comme document
    assert all(d.id != "queries" for d in docs)
    assert all(d.text for d in docs)
