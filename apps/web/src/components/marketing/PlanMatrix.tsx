import { PLAN_NAME } from "@/lib/copy";
import { MATRIX, MATRIX_PLANS, TRIAL_DAYS, rowCell } from "@/lib/marketing/plan-matrix";

import { ValueChip } from "@/components/site/StatusChip";

import { Ico } from "./landing/Ico";
import { MATRIX_GROUP_ICONS } from "./page-icons";

/**
 * Every plan limit side by side (GR-37), from lib/marketing/plan-matrix.ts: the numbers are the
 * API's own plan table, so a limit changed in billing/plans.py changes this page when the table
 * file is refreshed (the API's unit test fails until it is). Max is shown as coming soon; it can't
 * be bought yet.
 *
 * C-159 look, as the comparison tables: one fixed column grid for every group, so the plan columns
 * line up from table to table; Pro's column on a quiet tone step; "Included" and "Not included" as
 * chips with an icon; each group's caption with its icon. A phone scrolls a table inside its own box.
 */
export function PlanMatrix() {
  return (
    <section id="compare-plans" aria-labelledby="compare-plans-title" className="band pp scroll-mt-24">
      <div className="wrap">
        <div className="split-head">
          <h2 id="compare-plans-title" className="h-sec">
            Compare every limit
          </h2>
          <p className="lede">
            Limits are on features, never on how many contacts you have. Pro has a {TRIAL_DAYS.pro}-day free trial, once per workspace.
            Max is coming soon and can&apos;t be bought yet.
          </p>
        </div>
        <div className="mx after-head">
          {MATRIX.map((group) => {
            const icon = MATRIX_GROUP_ICONS[group.id];
            return (
              <div key={group.id} role="region" aria-label={group.title} tabIndex={0} className="ctable-box">
                <table className="ctable mtable-l">
                  <caption>
                    <span className="cap-in">
                      {icon ? <Ico icon={icon} /> : null}
                      {group.title}
                    </span>
                  </caption>
                  <colgroup>
                    <col className="c-feat" />
                    {MATRIX_PLANS.map((plan) => (
                      <col key={plan} />
                    ))}
                  </colgroup>
                  <thead>
                    <tr>
                      <th scope="col">Limit</th>
                      {MATRIX_PLANS.map((plan) => (
                        <th key={plan} scope="col" className={plan === "pro" ? "ours" : undefined}>
                          {PLAN_NAME[plan]}
                          {plan === "max" ? <span className="th-note">Coming soon</span> : null}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {group.rows.map((row) => (
                      <tr key={row.key}>
                        <th scope="row">
                          {row.label}
                          {row.note ? <span className="th-note">{row.note}</span> : null}
                        </th>
                        {MATRIX_PLANS.map((plan) => (
                          <td key={plan} className={plan === "pro" ? "ours num" : "num"}>
                            <ValueChip value={rowCell(row, plan)} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
        <p className="mx-foot">
          Catalogue and sequence limits are our current proposals and may change before launch. Plans don&apos;t include Meta&apos;s WhatsApp
          messaging fees, which Meta charges to your business.
        </p>
      </div>
    </section>
  );
}
