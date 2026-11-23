/**
 * The test of the formatter of the money of the replay, and of the formatter of the percentage of the replay.
 *
 * Why this test exists: the amounts of a recorded run are decimal text, and the interface has to show them exactly as
 * the recording wrote them. A binary float of a financial amount is a different amount, so the formatter never turns
 * the text into a number. It groups the digits of the integer part, it never rounds, it never pads the fraction with
 * zeros and it never repairs an amount that does not follow the grammar of a decimal.
 *
 * Why the test of the percentage is in the same file: a percentage is not money, it never carries the currency of the
 * run, and it is grouped with the very same rule as the money. The two formatters live side by side so that the rule
 * of the digits of the site is written in one place.
 *
 * Why the live mode is not in this file: the live mode carries the cost of a model, which is a different fact with a
 * different unit, and it renders the decimal text of the server without this module. The rule of the money of the
 * recorded demo lives in the module of the formatter, and it does not cover the live mode.
 *
 * Every case runs with no key and no network: the formatter is a pure function of the text it is given.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { MONEY_UNAVAILABLE, formatMoney, formatPercentage } from "@/lib/format/money";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("the formatter of the money", () => {
  it("writes the amount with the explicit code of the currency", () => {
    // It proves that the reader sees the amount and the currency of the recording, in that order.
    expect(formatMoney("566.79", "BRL")).toBe("BRL 566.79");
  });

  it("groups the integer part with the separator of the locale", () => {
    // It proves that the grouping changes no digit and no sign of the amount.
    expect(formatMoney("1234.56", "BRL")).toBe("BRL 1,234.56");
  });

  it("groups the integer part with the comma of the locale en-US, on any machine", () => {
    // It proves that the grouping does not depend on the locale of the machine that serves the site: the integer part
    // is grouped with the comma of the locale en-US, so the same amount reads the same way everywhere.
    expect(formatMoney("1000", "BRL")).toBe("BRL 1,000");
    expect(formatMoney("1234567.89", "BRL")).toBe("BRL 1,234,567.89");
    expect(formatMoney("-1234567.89", "BRL")).toBe("BRL -1,234,567.89");
  });

  it("keeps a fraction of more than two places exactly as it was written", () => {
    // It proves that the formatter never cuts and never rounds the fraction of an amount.
    expect(formatMoney("5.4931", "BRL")).toBe("BRL 5.4931");
  });

  it("says that the currency is not available when the recording carries no currency", () => {
    // It proves that the interface never assumes the currency of the run.
    expect(formatMoney("566.79", null)).toBe("566.79, currency not available");
  });

  it("says that the amount is not available when the recording carries no amount", () => {
    // It proves that a missing amount is rendered as unavailable and never as a zero.
    expect(formatMoney(null, "BRL")).toBe(MONEY_UNAVAILABLE);
    expect(formatMoney(undefined, undefined)).toBe(MONEY_UNAVAILABLE);
  });

  it("shows a malformed amount as it was read, after the code of the currency", () => {
    // It proves that the formatter never repairs an amount, because a repair would be an invention.
    expect(formatMoney("12,3x", "BRL")).toBe("BRL 12,3x");
  });

  it("keeps the sign of a negative amount", () => {
    // It proves that the grouping of the integer part never touches the sign.
    expect(formatMoney("-17.48", "BRL")).toBe("BRL -17.48");
  });

  it("never turns the amount into a number", () => {
    // It proves that the amount stays text from the first character to the last: a binary float of a financial amount
    // is a different amount.
    const number = vi.spyOn(globalThis, "Number");
    const parseFloat = vi.spyOn(globalThis, "parseFloat");
    const bigInt = vi.spyOn(globalThis, "BigInt");

    formatMoney("1234.56", "BRL");
    formatMoney("566.79", null);
    formatMoney("12,3x", "BRL");

    expect(number).not.toHaveBeenCalled();
    expect(parseFloat).not.toHaveBeenCalled();
    expect(bigInt).not.toHaveBeenCalled();
  });

  it("writes the code of the currency in upper case", () => {
    // It proves that the currency is written as the ISO 4217 code, in upper case, and never as it was read.
    expect(formatMoney("566.79", "brl")).toBe("BRL 566.79");
  });

  it("never pads the fraction of an amount with zeros", () => {
    // It proves that the formatter never invents the places of the fraction: the amount is shown as it was written.
    expect(formatMoney("5.5", "BRL")).toBe("BRL 5.5");
    expect(formatMoney("5", "BRL")).toBe("BRL 5");
  });

  it("keeps every digit of an amount that a float would lose", () => {
    // It proves that the formatter is exact: the digits that a double cannot hold are still on the screen.
    expect(formatMoney("0.1000000000000000055511151231257827", "BRL")).toBe(
      "BRL 0.1000000000000000055511151231257827",
    );
  });

  it("reads the separator of the fixed locale en-US and never the locale of the machine", async () => {
    // It proves that the locale of the formatter is FIXED and never the one of the machine that runs it.
    //
    // Why the case reads the locale that the formatter asks for and not the text of the separator: the machine of
    // this case has the locale `en-US`, so a separator that comes from the machine looks exactly like a separator that
    // comes from the fixed locale. The only way to tell the two apart is to watch the locale the formatter asks
    // `Intl` for, and the case watches it through a stand in for `Intl.NumberFormat` that records it.
    //
    // Why the module is read again: the formatter keeps the separator it read in a variable of its own, so a case that
    // wants to watch the very first reading has to hold a module that read nothing yet.
    vi.resetModules();

    const recorded: Array<string | string[] | undefined> = [];
    const OriginalNumberFormat = Intl.NumberFormat;
    const RecordingNumberFormat = function (
      locales?: string | string[],
      options?: Intl.NumberFormatOptions,
    ): Intl.NumberFormat {
      recorded.push(locales);
      return new OriginalNumberFormat(locales, options);
    } as unknown as typeof Intl.NumberFormat;

    vi.stubGlobal(
      "Intl",
      Object.assign(Object.create(Intl) as object, { NumberFormat: RecordingNumberFormat }),
    );

    const fresh = await import("@/lib/format/money");

    // only the reading of the separator is watched, so that nothing else of the runtime can be counted here
    recorded.length = 0;
    fresh.formatMoney("1234567.89", "BRL");

    expect(recorded.length).toBeGreaterThan(0);
    for (const locale of recorded) {
      expect(locale, "the formatter has to ask for the fixed locale en-US and never for the locale of the machine").toBe(
        "en-US",
      );
    }

    // the amount itself survives the grouping exactly as it was written
    expect(fresh.formatMoney("1234567.89", "BRL")).toBe("BRL 1,234,567.89");
  });
});

describe("the formatter of the percentage", () => {
  it("writes the percentage with the symbol of the percentage and with no currency", () => {
    // It proves that a percentage is not money: the symbol of the percentage is the unit of the value, and the currency
    // of the run never reaches it.
    expect(formatPercentage("2.50")).toBe("2.50%");
  });

  it("groups the integer part with the separator of the locale en-US", () => {
    // It proves that the percentage is grouped with the same rule as the money: the digits of the integer part receive
    // the separator of the locale en-US and the fraction is left alone.
    expect(formatPercentage("1234.5")).toBe("1,234.5%");
    expect(formatPercentage("1234567.891")).toBe("1,234,567.891%");
    expect(formatPercentage("1000")).toBe("1,000%");
  });

  it("keeps the fraction exactly as it was written", () => {
    // It proves that the formatter never rounds a percentage and never pads its fraction with zeros.
    expect(formatPercentage("2.5")).toBe("2.5%");
    expect(formatPercentage("2.500")).toBe("2.500%");
    expect(formatPercentage("2.4999")).toBe("2.4999%");
  });

  it("keeps the sign of a negative percentage", () => {
    // It proves that the grouping of the integer part never touches the sign.
    expect(formatPercentage("-2.50")).toBe("-2.50%");
    expect(formatPercentage("-1234.5")).toBe("-1,234.5%");
  });

  it("says that the percentage is not available when the recording carries none", () => {
    // It proves that a missing percentage is rendered as unavailable and never as a zero.
    expect(formatPercentage(null)).toBe(MONEY_UNAVAILABLE);
    expect(formatPercentage(undefined)).toBe(MONEY_UNAVAILABLE);
    expect(formatPercentage("")).toBe(MONEY_UNAVAILABLE);
    expect(formatPercentage("   ")).toBe(MONEY_UNAVAILABLE);
  });

  it("says that the percentage is not available when the value is not a decimal", () => {
    // It proves that the formatter never repairs a value and never writes a unit on a broken one.
    expect(formatPercentage("12,3x")).toBe(MONEY_UNAVAILABLE);
    expect(formatPercentage("2.5%")).toBe(MONEY_UNAVAILABLE);
    expect(formatPercentage("NaN")).toBe(MONEY_UNAVAILABLE);
  });

  it("never writes a number that was not in the recording", () => {
    // It proves that the formatter never produces NaN and never invents a value.
    for (const value of ["", " ", "abc", "12,3x", "NaN", "Infinity", "1e5"]) {
      expect(formatPercentage(value)).not.toContain("NaN");
    }
    expect(formatPercentage("1e5")).toBe(MONEY_UNAVAILABLE);
  });

  it("never turns the percentage into a number", () => {
    // It proves that the percentage stays text from the first character to the last: the grouping of the digits is
    // string work.
    const number = vi.spyOn(globalThis, "Number");
    const parseFloat = vi.spyOn(globalThis, "parseFloat");
    const bigInt = vi.spyOn(globalThis, "BigInt");

    formatPercentage("2.50");
    formatPercentage("1234.5");
    formatPercentage(null);
    formatPercentage("12,3x");

    expect(number).not.toHaveBeenCalled();
    expect(parseFloat).not.toHaveBeenCalled();
    expect(bigInt).not.toHaveBeenCalled();
  });
});
