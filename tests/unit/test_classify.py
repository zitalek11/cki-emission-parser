from cki_emission_parser.parsing.classify import classify_document


def test_classifies_issuance_decision_by_heading() -> None:
    doc_type, confidence = classify_document(
        "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ\nНоминальная стоимость каждой ценной бумаги",
        "decision.pdf",
    )
    assert doc_type == "issuance_decision"
    assert confidence > 0.4


def test_unknown_type_is_not_an_error() -> None:
    doc_type, confidence = classify_document("Служебная записка отдела кадров", "note.pdf")
    assert doc_type == "unknown"
    assert confidence == 0.0


def test_program_is_not_decision_when_heading_says_program() -> None:
    text = (
        "ПРОГРАММА БИРЖЕВЫХ ОБЛИГАЦИЙ серии 002P\n"
        "Далее в настоящем документе: Решение о выпуске — решение о выпуске "
        "ценных бумаг, закрепляющее совокупность прав."
    )
    doc_type, _ = classify_document(text, "Программа+биржевых+облигаций+серии+002P.pdf")
    assert doc_type == "bond_program"


def test_does_not_hardcode_issuer_names() -> None:
    gazprom, _ = classify_document("Решение о выпуске ценных бумаг ПАО «Газпром»", "a.pdf")
    rzd, _ = classify_document("Решение о выпуске ценных бумаг ОАО «РЖД»", "b.pdf")
    assert gazprom == rzd == "issuance_decision"
