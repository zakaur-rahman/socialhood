import Image from "next/image";

import { SITE_NAME } from "@/lib/marketing/site";

import { ContainerScroll } from "./effects/container-scroll-animation";
import { Container, SectionHeading } from "./primitives";
import { SHOTS } from "./shots";

/**
 * The real product, right after the hero (C-141): the inbox screenshot that used to sit under the
 * headline, with the same tilt-into-place as it scrolls in (ContainerScroll, still with reduced
 * motion) and its example-data caption.
 */
export function ProductShot() {
  return (
    <section aria-labelledby="inbox-shot-title" className="relative py-16 sm:py-20">
      <Container>
        <SectionHeading
          id="inbox-shot-title"
          eyebrow="See the inbox"
          title="Where every conversation lands"
          intro="Conversations on the left, the chat in the middle, and the AI's draft waiting for you to send, edit or dismiss."
        />
        <figure className="relative mx-auto mt-12 max-w-5xl">
          <div aria-hidden className="pointer-events-none absolute -inset-x-6 -top-10 -bottom-6 -z-10 rounded-3xl bg-glow-brand-top blur-2xl" />
          <ContainerScroll>
            <Image
              src={SHOTS.inbox.src}
              width={SHOTS.inbox.width}
              height={SHOTS.inbox.height}
              alt={SHOTS.inbox.alt}
              sizes="(min-width: 1072px) 1008px, calc(100vw - 2.5rem)"
              className="h-auto w-full"
            />
          </ContainerScroll>
          <figcaption className="mt-4 text-center text-xs text-fg-secondary">
            The {SITE_NAME} inbox with example data. The shop, people and messages are made up.
          </figcaption>
        </figure>
      </Container>
    </section>
  );
}
