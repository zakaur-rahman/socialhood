import { ScrollBox } from "@/components/site/ScrollBox";
import { SUBPROCESSORS, type Subprocessor } from "@/lib/subprocessors";

/**
 * The subprocessor table (C-156), from the one list in lib/subprocessors.ts. Rendered inside the
 * legal prose, which styles the table; it scrolls sideways on a phone rather than squeezing.
 */
export function SubprocessorTable({ rows = SUBPROCESSORS }: { rows?: readonly Subprocessor[] }) {
  return (
    <ScrollBox label="The service providers that process personal data for us">
      <table>
        <caption className="sr-only">The service providers that process personal data for us</caption>
        <thead>
          <tr>
            <th scope="col">Provider</th>
            <th scope="col">Purpose</th>
            <th scope="col">Data involved</th>
            <th scope="col">Location</th>
            <th scope="col">Terms</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <th scope="row" className="font-semibold text-fg">
                {row.name}
              </th>
              <td>
                {row.purpose}
                {row.note ? <span className="mt-1 block text-xs">{row.note}</span> : null}
              </td>
              <td>{row.data}</td>
              <td>{row.location}</td>
              <td>
                <a href={row.terms.href} rel="noopener noreferrer">
                  {row.terms.label}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollBox>
  );
}
