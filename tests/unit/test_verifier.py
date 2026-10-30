from phantomshell.verify import verify_conclusion


def test_verifier_rejects_forged_quote() -> None:
    result = {"verdict": "supported", "cause": "bad", "supporting": [
        {"claim": "bad", "evidence_id": "E1", "quote": "not in the event"}], "next_steps": [], "narrative": ""}
    checked = verify_conclusion(result, {"E1": "The actual event text."})
    assert checked["verdict"] == "inconclusive"
    assert checked["cause"] == "Insufficient verified evidence to support a cause."
    assert checked["supporting"] == []
    assert len(checked["unverified"]) == 1


def test_verifier_accepts_whitespace_normalized_quote() -> None:
    result = {"verdict": "supported", "cause": "x", "supporting": [
        {"claim": "x", "evidence_id": "T1", "quote": "entry point not found"}], "next_steps": [], "narrative": ""}
    checked = verify_conclusion(result, {"T1": "ERROR: entry   point not found: src/app.py"})
    assert checked["verdict"] == "supported"


def test_verifier_rejects_missing_evidence_id() -> None:
    result = {"verdict": "supported", "cause": "x", "supporting": [
        {"claim": "x", "evidence_id": "missing", "quote": "present"}], "next_steps": [], "narrative": ""}
    checked = verify_conclusion(result, {"E1": "present"})
    assert checked["verdict"] == "inconclusive"
    assert checked["supporting"] == []
