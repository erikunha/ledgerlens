---
document: fx-reference-rates
title: Reference exchange rates
topic: fx
version: 2026-10-01
language: en
---

# Acme Payments reference exchange rates

## Overview {#overview}

The reference exchange rate is the market value used to compare with the rate the merchant applied in a conversion. This policy says which source to use, how to handle weekends and holidays and what to do when the rate is not available.

## Official source {#source}

The reference rate is the European Central Bank's daily rate, obtained through the Frankfurter service in the version that uses only that source. On weekends and holidays the rate of the previous business day applies. The reference rate is a market reference and not the rate the merchant or the acquirer applied: the applied rate lives on the conversion record.

## Weekends and holidays {#weekends-holidays}

The European Central Bank publishes rates only on business days. For a Saturday, Sunday or holiday date, the lookup returns the rate of the last business day and reports the date actually used. The answer to the analyst must cite both dates, the requested one and the one used, so no one mistakes a Friday rate for a Saturday one.

## Why sources are not blended {#no-blended-sources}

Some versions of the service blend several central bank sources and can return a rate several percent above the European Central Bank's. A difference that large looks like a merchant markup and is not one. That is why the platform only accepts the single European Central Bank source and records the source name in each piece of evidence.

## Second source for the real {#second-source}

For pairs involving the Brazilian real, the Banco Central do Brasil publishes the closing PTAX rate, which serves as a cross-check. PTAX and the European Central Bank rate can differ by tenths of a percentage point, because they measure different times and markets. The default source is still the European Central Bank, and PTAX only comes in when the analysis asks for it.

## Decimal places {#decimals}

Rates are handled with four decimal places and compared as exact decimal numbers, never as floating point numbers. A cross rate, for example US dollar to Brazilian real, is computed through the euro and rounded to four places with round half to even. Differences in the fourth place are usually rounding.

## Available currencies {#supported-currencies}

The European Central Bank list has about thirty currencies, among them the euro, the US dollar, the Brazilian real, the pound sterling, the Swiss franc and the Canadian dollar. Currencies outside the list, such as the Argentine peso, have no reference rate. A future date, or one before the start of the series, has no rate either.

## Currency with no rate {#unsupported-currency-handling}

When the currency has no reference rate, the analyst must not make up an estimate or use another source without saying so. The answer says the reference rate does not exist for that currency, states what prevents the comparison and points to what would resolve the case, for example an official source for that currency. The case goes to human review.

## Service unavailable {#service-unavailable}

If the rate service is down after retries, the analyst reports that the reference rate could not be looked up, concludes only what the record shows and lists the missing rate, with the pair and the date. The case is flagged for human review and the analysis does not fill in the missing number.

## How to compare with the applied rate {#comparing-with-applied}

The implied markup is one minus the applied rate divided by the reference rate on the refund date, expressed as a percentage. A result close to zero means the merchant applied the reference rate. A positive result up to 3.0% is consistent with the markup plan. Above 3.0% the case must be escalated.

## Rounding tolerance {#rounding-tolerance}

An implied markup of up to ten hundredths of a percentage point can come from rate rounding alone. To say the merchant applies "about" a certain percentage, the analyst must check whether the computed value falls within a band of plus or minus five hundredths of a percentage point of that number, and show the band.

## Rate evidence {#rate-evidence}

Every rate cited in an answer carries the source, the currency pair, the requested date, the date used and the value. That information lives on the lookup record and makes it possible to redo the analysis. A rate with no source and no date cannot support a numeric conclusion.
