import clsx from "clsx";
import { CheckCircle2, CircleDashed } from "lucide-react";

import type { CoverageDetail } from "@/lib/types";

/** Which requirements the text addresses. Covered and missing differ by icon and label, not just color. */
export function RequirementList({ details, limit }: { details: CoverageDetail[]; limit?: number }) {
  const shown = limit ? details.slice(0, limit) : details;
  if (!details.length) return <p className="text-small text-ink-3">No requirements were extracted from the RFP.</p>;
  return (
    <ul className="flex flex-col">
      {shown.map((d) => (
        <li key={d.requirement} className="flex gap-2.5 border-b border-line py-2 last:border-0">
          {d.covered ? (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" aria-label="Addressed" />
          ) : (
            <CircleDashed className="mt-0.5 size-4 shrink-0 text-warn" aria-label="Not addressed" />
          )}
          <div className="min-w-0">
            <p className={clsx("text-small", d.covered ? "text-ink" : "text-ink-2")}>{d.requirement}</p>
            {!d.covered && <p className="text-caption text-ink-3">Not clearly addressed yet</p>}
          </div>
        </li>
      ))}
      {limit && details.length > limit && (
        <li className="pt-2 text-caption text-ink-3">{details.length - limit} more in the full list</li>
      )}
    </ul>
  );
}
