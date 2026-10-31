import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { TocNav } from "@/components/site/TocNav";

import { STAGES } from "./content";
import { StageVisual } from "./visuals";

/**
 * The flow of /how-it-works (C-160): the step tracker beside the stages on a wide screen (sticky; the
 * current stage marked by toc-spy), and the stages as one ordered list down a line. Each stage is a
 * section with its number on the line, its heading, a short explanation and its scene. The line fills
 * with ink as the page scrolls past it where the browser has scroll timelines (site.css, C-160), and
 * stays a plain line elsewhere and with reduced motion. The numbers are the list's own order, shown
 * because the sequence is the point of the page.
 */
export function HowItWorksStages() {
  return (
    <div className="band xp-flow-band">
      <div className="wrap xp-flow">
        <aside className="xp-track">
          <TocNav items={STAGES.map((stage) => ({ id: stage.id, label: stage.short }))} label="The steps" numbered />
        </aside>
        <ol className="xp-stages" data-flow="">
          {STAGES.map((stage, index) => (
            <li key={stage.id} className={stage.wide ? "xp-stage is-wide" : "xp-stage"}>
              <section id={stage.id} aria-labelledby={`${stage.id}-title`} className="xp-stage-in">
                <span className="xp-mark num" aria-hidden>
                  {index + 1}
                </span>
                <div className="xp-copy">
                  <h2 id={`${stage.id}-title`} className="xp-h">
                    <span className="sr-only">Step {index + 1}: </span>
                    {stage.title}
                  </h2>
                  {stage.body.map((paragraph) => (
                    <p key={paragraph} className="xp-p">
                      {paragraph}
                    </p>
                  ))}
                  <ul className="xp-points">
                    {stage.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                  {stage.link ? (
                    <p className="xp-more">
                      <Link href={stage.link.href as Route} className="tlink">
                        {stage.link.label}
                        <ArrowRight className="size-4" aria-hidden />
                      </Link>
                    </p>
                  ) : null}
                </div>
                <div className="xp-vis">
                  <StageVisual id={stage.id} />
                </div>
              </section>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
