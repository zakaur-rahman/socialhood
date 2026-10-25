import Image from "next/image";
import type { CSSProperties } from "react";

import { CUSTOMER_LOGOS, TESTIMONIALS, type CustomerLogo, type Testimonial } from "@/lib/marketing/social-proof";

import { Container, MARKETING_CARD, SectionHeading } from "./primitives";

/**
 * Quotes and customer logos, from lib/marketing/social-proof.ts. With no data (today) it renders
 * nothing at all: no heading, no placeholder, no empty box (C-138).
 */
export function SocialProof({ testimonials = TESTIMONIALS, logos = CUSTOMER_LOGOS }: { testimonials?: Testimonial[]; logos?: CustomerLogo[] }) {
  if (testimonials.length === 0 && logos.length === 0) return null;
  return (
    <section aria-labelledby="proof-title" className="border-t border-line-subtle py-16 sm:py-20">
      <Container>
        <SectionHeading id="proof-title" eyebrow="Customers" title="In their words" />
        {testimonials.length > 0 ? (
          <ul className="mx-auto mt-12 grid max-w-5xl gap-4 md:grid-cols-3">
            {testimonials.map((item, index) => (
              <li key={item.name} data-reveal style={{ "--reveal-delay": `${(index % 3) * 80}ms` } as CSSProperties}>
                <figure className={`${MARKETING_CARD} flex h-full flex-col gap-4 p-5`}>
                  <blockquote className="text-sm leading-relaxed">{item.quote}</blockquote>
                  <figcaption className="mt-auto flex items-center gap-3">
                    {item.avatar ? (
                      <Image src={item.avatar.src} alt={item.avatar.alt} width={item.avatar.width} height={item.avatar.height} className="size-10 rounded-full object-cover" />
                    ) : null}
                    <span className="text-sm">
                      <span className="block font-semibold">{item.name}</span>
                      <span className="block text-fg-secondary">{item.role}</span>
                    </span>
                  </figcaption>
                </figure>
              </li>
            ))}
          </ul>
        ) : null}
        {logos.length > 0 ? (
          <ul aria-label="Businesses using the product" className="mx-auto mt-10 flex max-w-4xl flex-wrap items-center justify-center gap-x-10 gap-y-6">
            {logos.map((logo) => (
              <li key={logo.name}>
                <Image src={logo.src} alt={logo.name} width={logo.width} height={logo.height} className="h-8 w-auto opacity-80" />
              </li>
            ))}
          </ul>
        ) : null}
      </Container>
    </section>
  );
}
