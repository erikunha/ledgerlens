/**
 * The formatter of the money of the replay, and the formatter of the percentage of the replay.
 *
 * Why this file exists: the amounts of a recorded run are decimal text, and the interface has to show them without
 * ever turning them into a binary float. A binary float of a financial amount is a different amount, so this
 * formatter groups the digits of the integer part and does nothing else. It never multiplies, never rounds, never
 * pads the fraction with zeros and never repairs an amount that does not follow the grammar of a decimal.
 *
 * Why the rule of the money of the RECORDED demo lives here: every amount that comes out of a recorded run is read
 * through this module, so the recorded demo has exactly one rule about the money it shows. The live mode is a
 * different fact with a different unit: it carries the cost of a model, which is the price of a run and not an
 * amount of a payment, and that panel renders the decimal text the server sent without this module. The two are
 * kept apart on purpose, because they are two different facts and one rule about the money of the site would hide
 * that difference.
 *
 * Why the formatter of the percentage lives here too: a percentage of the breakdown is not money, it never carries the
 * currency of the run, and it is grouped with the very same rule as the money. The two formatters stand side by side,
 * so that the rule of the digits of the site is written in one place and the two units can never drift apart.
 */

/** What the interface shows when the recording carries no amount at all. */
export const MONEY_UNAVAILABLE = "Not available";

/** What the interface appends when the recording carries no currency for the amount. */
const CURRENCY_UNAVAILABLE_SUFFIX = ", currency not available";

/** The symbol of the percentage, which is the unit of a percentage and never a currency. */
const PERCENTAGE_SYMBOL = "%";

/** The grammar of a decimal amount: an optional sign, digits and an optional fraction. */
const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

/** The separator that groups the digits of the integer part, read from the fixed locale `en-US`. */
let groupSeparator: string | null = null;

/**
 * Reads the separator that groups the digits of the integer part.
 *
 * The separator is taken from the locale `en-US`, and never from the amount. The locale is fixed on purpose: the site
 * is a static export, so the separator that the server renders and the separator that the browser renders have to be
 * the same one, otherwise the same amount would be written two different ways. The formatted number is used only to
 * find the separator, so the amount itself is never handed to a number formatter.
 */
function readGroupSeparator(): string {
  if (groupSeparator !== null) {
    return groupSeparator;
  }
  try {
    const formatted = new Intl.NumberFormat("en-US").format(1000);
    // Only the digits are removed, so a separator that is a space of a locale stays a space.
    const separator = formatted.replace(/[0-9]/g, "");
    groupSeparator = separator.length > 0 && separator.length <= 2 ? separator : ",";
  } catch {
    // A runtime without a full ICU falls back to the comma, which never changes a digit and never changes a sign.
    groupSeparator = ",";
  }
  return groupSeparator;
}

/**
 * Groups the digits of the integer part of an amount.
 *
 * The sign, the digits and the fraction are kept exactly as they were written. Only the digits of the integer part
 * receive the separator of the locale `en-US`.
 */
function groupIntegerPart(digits: string, separator: string): string {
  if (digits.length <= 3) {
    return digits;
  }
  const groups: string[] = [];
  let end = digits.length;
  while (end > 3) {
    groups.unshift(digits.slice(end - 3, end));
    end -= 3;
  }
  groups.unshift(digits.slice(0, end));
  return groups.join(separator);
}

/**
 * Groups the integer part of an amount that follows the decimal grammar.
 *
 * The function works on the text. It never calls `Number`, never calls `parseFloat` and never builds a `BigInt`,
 * because every one of those turns a decimal into a binary float.
 */
function groupAmount(amount: string): string {
  const negative = amount.startsWith("-");
  const body = negative ? amount.slice(1) : amount;
  const dot = body.indexOf(".");
  const integerPart = dot === -1 ? body : body.slice(0, dot);
  const fractionPart = dot === -1 ? "" : body.slice(dot);
  const grouped = groupIntegerPart(integerPart, readGroupSeparator());
  return `${negative ? "-" : ""}${grouped}${fractionPart}`;
}

/**
 * Renders an amount with its currency.
 *
 * The amount is the decimal text the server or the artifact carries, for example `"566.79"`. It is read as text: the
 * fraction is kept exactly as it was written and the integer part is only grouped with the separator of the locale
 * `en-US`, which is fixed so that the static export and the browser write the same amount the same way.
 * The currency is the explicit ISO 4217 code in upper case; a currency that is not three letters is shown as it was
 * read, never guessed and never mapped to a country.
 *
 * A missing amount gives `MONEY_UNAVAILABLE`. A missing currency gives the grouped amount followed by
 * `, currency not available`, because the interface never assumes the currency of the run. An amount that does not
 * follow the grammar of a decimal is shown as it was read, after the currency code, because a repair is an invention.
 */
export function formatMoney(amount: string | null | undefined, currency: string | null | undefined): string {
  const amountText = typeof amount === "string" ? amount.trim() : "";
  if (amountText === "") {
    return MONEY_UNAVAILABLE;
  }

  const currencyText = typeof currency === "string" ? currency.trim() : "";
  const shown = DECIMAL_PATTERN.test(amountText) ? groupAmount(amountText) : amountText;

  if (currencyText === "") {
    return `${shown}${CURRENCY_UNAVAILABLE_SUFFIX}`;
  }

  // A currency of three letters is an ISO 4217 code and is written in upper case. Anything else is shown as it was
  // read, because the interface does not know what the recording meant by it.
  const code = /^[A-Za-z]{3}$/.test(currencyText) ? currencyText.toUpperCase() : currencyText;
  return `${code} ${shown}`;
}

/**
 * Renders a percentage with the symbol of the percentage.
 *
 * A percentage is not money: it never carries the currency of the run, so the formatter takes no currency and writes
 * none. The symbol of the percentage goes right after the digits, with no space, so that a reader never has to guess
 * the unit of a number that sits among money values.
 *
 * The percentage is read as text, exactly like an amount: the fraction is kept as it was written, it is never rounded
 * and never padded with zeros, and the integer part is only grouped with the separator of the locale `en-US`, which
 * is the same rule the money follows.
 *
 * A missing percentage gives `MONEY_UNAVAILABLE`, and so does a value that does not follow the grammar of a decimal.
 * The money shows a broken amount as it was read, after the code of the currency; a percentage has no currency to
 * carry that text, and a unit written on a broken value would be an invention, so the interface says that the
 * percentage is not available.
 */
export function formatPercentage(percentage: string | null | undefined): string {
  const text = typeof percentage === "string" ? percentage.trim() : "";
  if (text === "" || !DECIMAL_PATTERN.test(text)) {
    return MONEY_UNAVAILABLE;
  }
  return `${groupAmount(text)}${PERCENTAGE_SYMBOL}`;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the formatter at once. */
export const __all__ = ["MONEY_UNAVAILABLE", "formatMoney", "formatPercentage"] as const;
