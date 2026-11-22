/**
 * The switcher of the accounts of the recording.
 *
 * Why this file exists: the artifact of the ledger of a scenario publishes a LIST of accounts,
 * even when it holds only one, because a recording that reads many accounts publishes many
 * accounts. The switcher is the control that chooses which one of them is on the screen, and it
 * is drawn the same way whether the artifact holds one account or many, so that the shape of the
 * control never changes under the visitor.
 *
 * Why the chosen account carries the state of the pressed button: the state of the visit is never
 * only a colour, and `aria-pressed` is a state a reader of a screen reader hears.
 *
 * Why the account never goes in the URL: the state of the visitor lives in the memory of the
 * panel, and the query string of the route carries the tab and the speed and nothing else
 * (ADR-043, ADR-045).
 */

import type { ReactElement } from "react";

import type { LedgerAccount } from "@/lib/api/schemas";

/** The identifier of the label of the group, so that the group is named by the text it shows. */
const LABEL_ID = "ledgerlens-ledger-accounts-label";

/** The label of the group of the accounts, the accessible name of the switcher. */
const GROUP_LABEL = "The accounts of the recording";

/** The sentence that says in words that the recording read the ledger of one account. */
const ONE_ACCOUNT = "The recording read the ledger of one account.";

/**
 * The props of the switcher of the accounts.
 *
 * Why the switcher takes the accounts and not the artifact: the switcher draws a list of buttons
 * and it never reads the artifact itself, so the panel stays the one place that reads it.
 */
export interface AccountSwitcherProps {
  /** The accounts the artifact publishes. */
  readonly accounts: readonly LedgerAccount[];
  /** The account that is on the screen. */
  readonly selectedAccountId: string;
  /** Called when the visitor chooses another account. */
  readonly onSelectAccount: (accountId: string) => void;
}

/**
 * Writes the name of an account as a visitor reads it.
 *
 * Why the identifier comes first: the identifier is the identity of the account, and the name of
 * the simulated customer is a decoration of it.
 */
function accountName(account: LedgerAccount): string {
  const name = typeof account.name === "string" ? account.name.trim() : "";
  return name === "" ? account.id : `${account.id}, ${name}`;
}

/**
 * The switcher of the accounts of the recording.
 *
 * The switcher draws the accounts of the artifact as buttons of a group, it says in words that the
 * recording read the ledger of one account when the artifact holds one account, and it hands the
 * account the visitor picks back to the panel.
 */
export function AccountSwitcher({
  accounts,
  selectedAccountId,
  onSelectAccount,
}: AccountSwitcherProps): ReactElement {
  return (
    <div className="ll-ledger-switcher">
      <p id={LABEL_ID} className="ll-ledger-switcher-label">
        {GROUP_LABEL}
      </p>

      <div role="group" aria-labelledby={LABEL_ID} className="ll-ledger-accounts">
        {accounts.map((account) => {
          const isSelected = account.id === selectedAccountId;
          return (
            <button
              key={account.id}
              type="button"
              aria-pressed={isSelected}
              className={isSelected ? "ll-ledger-account ll-ledger-account-pressed" : "ll-ledger-account"}
              onClick={() => onSelectAccount(account.id)}
            >
              {accountName(account)}
            </button>
          );
        })}
      </div>

      {accounts.length === 1 ? <p className="ll-ledger-note">{ONE_ACCOUNT}</p> : null}
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the switcher at once. */
export const __all__ = ["AccountSwitcherProps", "AccountSwitcher"] as const;
