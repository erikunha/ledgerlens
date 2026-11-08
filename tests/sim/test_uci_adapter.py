"""UCI Online Retail II adapter: invoice aggregation, service-line filter, cancellation linking.

Uses a 40-row mini file (`tests/fixtures/uci_mini.csv`) whose rows cover each rule once.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.sim.sources.base import SourceInvoice
from ledgerlens.sim.sources.uci import (
    SERVICE_STOCK_CODES,
    UciSource,
    ensure_csv,
    link_cancellations,
)

MINI = Path(__file__).resolve().parents[1] / "fixtures" / "uci_mini.csv"


@pytest.fixture(scope="module")
def invoices() -> dict[str, SourceInvoice]:
    return {inv.source_ref: inv for inv in UciSource(MINI).iter_invoices()}


def test_mini_file_has_forty_data_rows():
    assert len(MINI.read_text().splitlines()) == 41


def test_lines_of_one_invoice_become_one_record(invoices):
    inv = invoices["600001"]
    assert inv.amount == Decimal("35.64")  # 6 x 2.55 + 6 x 3.39, postage dropped
    assert inv.currency == "GBP"
    assert inv.customer_ref == "12346"
    assert inv.country == "United Kingdom"
    assert inv.placed_at == datetime(2011, 10, 3, 9, 0)
    assert inv.is_cancellation is False


def test_stock_codes_list_the_dominant_line_first_and_skip_service_lines(invoices):
    assert invoices["600001"].stock_codes == ("71053", "85123A")  # 20.34 before 15.30
    assert "POST" not in invoices["600001"].stock_codes


def test_service_lines_are_dropped_and_service_only_invoices_vanish(invoices):
    assert {"POST", "DOT", "BANK CHARGES", "M", "AMAZONFEE", "ADJUST"} <= set(SERVICE_STOCK_CODES)
    assert invoices["600005"].amount == Decimal("25.50")  # DOTCOM POSTAGE of 40.00 ignored
    assert invoices["600016"].amount == Decimal("7.65")  # POST and M ignored
    assert "600010" not in invoices  # only a bank charge


def test_invoices_without_a_customer_are_dropped(invoices):
    assert "600008" not in invoices
    assert "C600107" not in invoices


def test_a_sale_with_a_non_positive_total_is_not_a_sale(invoices):
    assert "600011" not in invoices


def test_cancellations_are_flagged_and_negative(invoices):
    inv = invoices["C600101"]
    assert inv.is_cancellation is True
    assert inv.amount == Decimal("-8.40")
    assert invoices["C600102"].amount == Decimal("-62.68")


def test_invoices_come_out_in_time_order(invoices):
    times = [inv.placed_at for inv in UciSource(MINI).iter_invoices()]
    assert times == sorted(times)


def test_stats_count_what_was_dropped():
    source = UciSource(MINI)
    list(source.iter_invoices())
    stats = source.stats
    assert stats.rows == 40
    assert stats.dropped_no_customer == 2  # invoices, not rows
    assert stats.dropped_service_only == 1
    assert stats.dropped_non_positive == 1
    assert stats.invoices == 20  # 13 sales and 7 cancellations survive


def test_a_partial_cancellation_links_to_the_latest_earlier_sale_sharing_a_code(invoices):
    result = link_cancellations(invoices.values())
    link = next(item for item in result.links if item.cancellation.source_ref == "C600101")
    assert link.sale.source_ref == "600002"  # not 600001, which is older and also shares 85123A
    assert link.amount == Decimal("8.40")
    assert link.partial is True


def test_the_latest_sale_wins_even_when_an_older_one_matches_too(invoices):
    result = link_cancellations(invoices.values())
    link = next(item for item in result.links if item.cancellation.source_ref == "C600106")
    assert link.sale.source_ref == "600014"
    assert link.amount == Decimal("11.10")
    assert link.partial is True


def test_a_cancellation_that_covers_the_sale_is_a_full_refund(invoices):
    result = link_cancellations(invoices.values())
    link = next(item for item in result.links if item.cancellation.source_ref == "C600102")
    assert link.sale.source_ref == "600003"
    assert link.amount == Decimal("62.68")
    assert link.partial is False


def test_the_refund_never_exceeds_the_sale(invoices):
    result = link_cancellations(invoices.values())
    link = next(item for item in result.links if item.cancellation.source_ref == "C600105")
    assert link.sale.source_ref == "600012"
    assert link.amount == Decimal("11.80")  # cancellation was 42.50
    assert link.partial is False


def test_unlinked_cancellations_are_counted_not_hidden(invoices):
    result = link_cancellations(invoices.values())
    unlinked = {inv.source_ref for inv in result.unlinked}
    assert unlinked == {"C600103", "C600104"}  # no shared code; the only sale is later than the cancellation
    assert {item.cancellation.source_ref for item in result.links} == {
        "C600101",
        "C600102",
        "C600105",
        "C600106",
        "C600108",
    }
    assert result.cancellations == 7
    assert result.matching_rate == pytest.approx(5 / 7)


def test_linking_only_sees_the_sales_it_is_given(invoices):
    sales = [inv for inv in invoices.values() if not inv.is_cancellation and inv.source_ref != "600002"]
    cancel = invoices["C600101"]
    result = link_cancellations([*sales, cancel])
    link = next(item for item in result.links if item.cancellation.source_ref == "C600101")
    assert link.sale.source_ref == "600001", "falls back to the next latest sale that shares a stock code"
    result = link_cancellations([cancel])
    assert [inv.source_ref for inv in result.unlinked] == ["C600101"]


def test_an_empty_input_has_a_zero_matching_rate():
    result = link_cancellations([])
    assert result.cancellations == 0 and result.matching_rate == 0.0


def test_the_real_file_layout_reads_from_a_zip_of_xlsx_with_overlapping_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    header = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
    book = openpyxl.Workbook()
    first = book.active
    first.title = "Year 2009-2010"
    first.append(header)
    first.append([700001, 85048, "GLASS BALL", 2, datetime(2010, 12, 1, 8, 0), 5.5, 13085, "United Kingdom"])
    second = book.create_sheet("Year 2010-2011")
    second.append(header)
    second.append([700001, 85048, "GLASS BALL", 2, datetime(2010, 12, 1, 8, 0), 5.5, 13085, "United Kingdom"])
    second.append(["700002", "79323P", "CHERRY", 1, datetime(2011, 12, 9, 12, 0), 6.75, 13085.0, "United Kingdom"])
    xlsx = tmp_path / "online_retail_II.xlsx"
    book.save(xlsx)
    archive = tmp_path / "online_retail_ii.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(xlsx, "online_retail_II.xlsx")

    csv_path = ensure_csv(archive)
    found = {inv.source_ref: inv for inv in UciSource(archive).iter_invoices()}

    assert csv_path.exists() and csv_path != archive
    assert set(found) == {"700001", "700002"}
    assert found["700001"].amount == Decimal("11.00"), "the invoice in both sheets is counted once"
    assert found["700002"].customer_ref == "13085"
    assert ensure_csv(archive) == csv_path, "the converted file is reused"


def test_older_column_names_are_accepted(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text(
        "InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country\n"
        "500001,85123A,X,2,2011-01-04 10:00:00,2.50,17850,United Kingdom\n",
        encoding="utf-8",
    )
    (inv,) = list(UciSource(path).iter_invoices())
    assert inv.amount == Decimal("5.00") and inv.customer_ref == "17850"
