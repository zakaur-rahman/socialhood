import { PLAN_NAME } from "@/lib/copy";
import { MATRIX, MATRIX_PLANS, TRIAL_DAYS, rowCell } from "@/lib/marketing/plan-matrix";

import { Container } from "./primitives";

/**
 * Every plan limit side by side (GR-37), from lib/marketing/plan-matrix.ts: the numbers are the
 * API's own plan table, so a limit changed in billing/plans.py changes this page when the table
 * file is refreshed (the API's unit test fails until it is). Max is shown as coming soon; it can't
 * be bought yet.
 */
export function PlanMatrix() {
  return (
    <section id="compare-plans" aria-labelledby="compare-plans-title" className="scroll-mt-24 border-t border-line-subtle py-16 sm:py-20">
      <Container>
        <h2 id="compare-plans-title" className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Compare every limit
        </h2>
        <p className="mt-3 max-w-2xl text-base text-fg-secondary">
          Limits are on features, never on how many contacts you have. Pro has a {TRIAL_DAYS.pro}-day free trial, once per workspace. Max is
          coming soon and can&apos;t be bought yet.
        </p>
        {MATRIX.map((group) => (
          <div key={group.id} className="mt-10">
            <div
              role="region"
              aria-label={group.title}
              tabIndex={0}
              className="overflow-x-auto rounded-2xl border border-line bg-panel-glass focus-visible:outline-offset-2"
            >
              <table className="w-full min-w-[34rem] border-collapse text-left">
                <caption className="px-4 pt-4 text-left text-base font-semibold">{group.title}</caption>
                <thead>
                  <tr className="border-b border-line text-sm">
                    <th scope="col" className="px-4 py-3 font-medium text-fg-secondary">
                      Limit
                    </th>
                    {MATRIX_PLANS.map((plan) => (
                      <th key={plan} scope="col" className="px-4 py-3 font-semibold">
                        {PLAN_NAME[plan]}
                        {plan === "max" ? <span className="block text-xs font-normal text-fg-secondary">Coming soon</span> : null}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((row) => (
                    <tr key={row.key} className="border-b border-line-subtle align-top last:border-b-0">
                      <th scope="row" className="px-4 py-3 text-sm font-medium">
                        {row.label}
                        {row.note ? <span className="mt-1 block text-xs font-normal leading-relaxed text-fg-secondary">{row.note}</span> : null}
                      </th>
                      {MATRIX_PLANS.map((plan) => (
                        <td key={plan} className="px-4 py-3 text-sm tabular-nums">
                          {rowCell(row, plan)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-fg-secondary">
          Catalogue and sequence limits are our current proposals and may change before launch. Plans don&apos;t include Meta&apos;s WhatsApp
          messaging fees, which Meta charges to your business.
        </p>
      </Container>
    </section>
  );
}
