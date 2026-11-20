import copy
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from unittest.mock import Mock, call, patch

import requests

from scripts import tw_margin_balances as report
from stock_bot.market.twse import MARGIN_URL, TwseRepository


DAY = date(2026, 11, 19)
# Actual MI_MARGN total table fetched for 2026-11-19.
PAYLOAD = {
    "stat": "OK",
    "date": "20261119",
    "tables": [{
        "title": "115年11月19日 信用交易統計",
        "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
        "data": [
            ["融資(交易單位)", "494,619", "625,396", "13,869", "9,092,265", "8,947,619"],
            ["融券(交易單位)", "25,452", "47,343", "5,616", "193,544", "209,819"],
            ["融資金額(仟元)", "21,627,629", "41,316,390", "3,969,551", "508,026,642", "484,368,330"],
        ],
    }, {}],
}


def parse(payload=PAYLOAD):
    response = Mock()
    response.json.return_value = payload
    with patch("stock_bot.market.twse.requests.get", return_value=response) as get:
        rows = TwseRepository().fetch_margin_balances(DAY)
    return rows, get


class MarginRepositoryTests(unittest.TestCase):
    def test_actual_table_and_request_parameters(self):
        rows, get = parse()
        self.assertEqual(rows["financing_amount"]["今日餘額"], 484_368_330)
        self.assertEqual(rows["short_units"]["今日餘額"], 209_819)
        self.assertEqual(rows["financing_units"]["今日餘額"], 8_947_619)
        get.assert_called_once_with(
            MARGIN_URL, params={"date": "20261119", "selectType": "MS", "response": "json"}, timeout=15,
        )

    def test_no_data_is_not_zero(self):
        for status in ("很抱歉，沒有符合條件的資料！", {"stat": "很抱歉，沒有符合條件的資料!"}):
            with self.subTest(status=status):
                self.assertIsNone(parse({"stat": status})[0])

    def test_rejects_wrong_date_and_malformed_reports(self):
        mutations = [
            lambda p: p.update(date="20261118"),
            lambda p: p.update(stat="ERROR"),
            lambda p: p.update(tables=[]),
            lambda p: p["tables"][0]["fields"].__setitem__(1, "賣出"),
            lambda p: p["tables"][0]["data"].pop(),
            lambda p: p["tables"][0]["data"].append(p["tables"][0]["data"][0]),
            lambda p: p["tables"][0]["data"][0].pop(),
            lambda p: p["tables"][0]["data"][0].__setitem__(1, "--"),
            lambda p: p["tables"][0]["data"][0].__setitem__(1, "-1"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                payload = copy.deepcopy(PAYLOAD)
                mutate(payload)
                with self.assertRaises(ValueError):
                    parse(payload)

    def test_reordered_fields_and_tables(self):
        payload = copy.deepcopy(PAYLOAD)
        table = payload["tables"][0]
        table["fields"].reverse()
        for row in table["data"]:
            row.reverse()
        payload["tables"].reverse()
        self.assertEqual(parse(payload)[0], parse()[0])

    def test_connection_failure(self):
        with patch("stock_bot.market.twse.requests.get", side_effect=requests.Timeout):
            with self.assertRaises(RuntimeError):
                TwseRepository().fetch_margin_balances(DAY)

    def test_invalid_json_is_a_format_error(self):
        response = Mock()
        response.json.side_effect = requests.exceptions.JSONDecodeError("invalid", "<html>", 0)
        with patch("stock_bot.market.twse.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "JSON"):
                TwseRepository().fetch_margin_balances(DAY)


class MarginReportTests(unittest.TestCase):
    def test_actual_card_amounts_deltas_and_all_details(self):
        payload = report.build_report(DAY, parse()[0])
        embed = payload["embeds"][0]
        self.assertIn("2026/11/19", embed["title"])
        values = [field["value"] for field in embed["fields"]]
        self.assertEqual(values[0], "**4,843.68 億元**\n較前日減少 236.58 億元")
        self.assertEqual(values[1], "**209,819 交易單位**\n較前日增加 16,275 交易單位")
        self.assertEqual(values[2], "買進　216.28 億元\n賣出　413.16 億元\n現金償還　39.70 億元")
        self.assertEqual(values[3], "賣出　47,343 交易單位\n買進回補　25,452 交易單位\n現券償還　5,616 交易單位")
        self.assertIn("次一交易日調整", embed["footer"]["text"])
        self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_zero_change_and_decimal_rounding(self):
        field = report.balance_field("融資餘額", {"今日餘額": 0, "前日餘額": 0}, report.format_amount)
        self.assertIn("持平 0.00 億元", field["value"])
        self.assertEqual(report.format_amount(100_500), "1.01 億元")

    @patch.object(report.time, "sleep")
    def test_retry_unpublished_then_connection_failure_then_success(self, sleep):
        rows = parse()[0]
        repository = Mock()
        repository.fetch_margin_balances.side_effect = [None, RuntimeError("timeout"), rows]
        with redirect_stderr(io.StringIO()):
            result = report.fetch_with_retries(repository, DAY, 9, 900)
        self.assertEqual(result, rows)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(repository.fetch_margin_balances.call_args_list, [call(DAY)] * 3)

    @patch.object(report.time, "sleep")
    def test_retry_exhaustion(self, sleep):
        repository = Mock()
        repository.fetch_margin_balances.return_value = None
        with redirect_stderr(io.StringIO()):
            self.assertIsNone(report.fetch_with_retries(repository, DAY, 9, 900))
        self.assertEqual(repository.fetch_margin_balances.call_count, 9)
        self.assertEqual(sleep.call_count, 8)
        repository.fetch_margin_balances.side_effect = RuntimeError("timeout")
        with self.assertRaises(RuntimeError):
            report.fetch_with_retries(repository, DAY, 1, 900)

    @patch.object(report.time, "sleep")
    def test_invalid_report_is_not_retried(self, sleep):
        repository = Mock()
        repository.fetch_margin_balances.side_effect = ValueError("wrong date")
        with self.assertRaises(ValueError):
            report.fetch_with_retries(repository, DAY, 9, 900)
        sleep.assert_not_called()

    def run_main(self, rows, extra_args=(), send_error=None):
        with (
            patch("sys.argv", ["tw_margin_balances", "--date", "2026-11-19", *extra_args]),
            patch.object(report, "TwseRepository") as repository,
            patch.object(report, "load_report_config") as config,
            patch.object(report, "DiscordWebhook") as webhook,
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()),
        ):
            repository.return_value.fetch_margin_balances.return_value = rows
            webhook.return_value.send.side_effect = send_error
            if send_error:
                with self.assertRaises(SystemExit) as exit:
                    report.main()
                self.assertEqual(exit.exception.code, 1)
            else:
                report.main()
        return config, webhook, output.getvalue()

    def test_dry_run_never_loads_secrets_or_sends(self):
        config, webhook, output = self.run_main(parse()[0], ["--dry-run"])
        config.assert_not_called()
        webhook.assert_not_called()
        self.assertIn('"status": "ok"', output)
        self.assertIn('"discord":', output)

    def test_no_data_never_sends(self):
        config, webhook, output = self.run_main(None)
        config.assert_not_called()
        webhook.assert_not_called()
        self.assertIn('"status": "no_data"', output)

    def test_success_sends_once_and_webhook_failure_does_not_retry(self):
        for error in (None, RuntimeError("webhook timeout")):
            with self.subTest(error=error):
                _, webhook, _ = self.run_main(parse()[0], ["--attempts", "9"], error)
                webhook.return_value.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
