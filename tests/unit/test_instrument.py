from tests.helpers import build_job

from cki_emission_parser.extraction.instrument import guess_instrument_class


def test_guesses_exchange_bond_from_wording() -> None:
    job = build_job("Решение о выпуске биржевых облигаций серии 001P-12")
    assert guess_instrument_class(job) == "bond_exchange"


def test_guesses_structured_bond() -> None:
    job = build_job("Решение о выпуске структурных облигаций")
    assert guess_instrument_class(job) == "bond_structured"


def test_guesses_pref_share() -> None:
    job = build_job("Решение о дополнительном выпуске привилегированных акций")
    assert guess_instrument_class(job) == "share_pref"


def test_unknown_when_no_instrument_language() -> None:
    job = build_job("Служебная записка о командировке")
    assert guess_instrument_class(job) == "unknown"


def test_disclaimer_not_structured_keeps_exchange_bond() -> None:
    job = build_job(
        "ПРОГРАММА БИРЖЕВЫХ ОБЛИГАЦИЙ. "
        "Биржевые облигации не являются структурными облигациями. "
        "Для структурных облигаций: не применимо.",
        filename="Программа биржевых облигаций серии 002P.pdf",
    )
    assert guess_instrument_class(job) == "bond_exchange"


def test_structured_from_title_without_filename_hint() -> None:
    job = build_job(
        "РЕШЕНИЕ О ВЫПУСКЕ ОБЛИГАЦИЙ. "
        "Структурные процентные дисконтные неконвертируемые облигации серии С-1.",
        filename="Решение о выпуске С-1-1759.docx",
    )
    assert guess_instrument_class(job) == "bond_structured"
