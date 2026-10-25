/**
 * Social proof for the landing page (C-138): what real customers have said, and which customers
 * allow their logo. There are none yet, so both lists are empty and the section renders nothing.
 * Add an entry only with the person's or business's written permission, and with words they
 * actually said; the page never invents or paraphrases one. Nothing else needs to change.
 */
export type Testimonial = {
  quote: string;
  name: string;
  /** Their role and business, as they want it shown. */
  role: string;
  /** A photo or logo in /public, with its own alt text. */
  avatar?: { src: string; alt: string; width: number; height: number };
};

export type CustomerLogo = {
  name: string;
  src: string;
  width: number;
  height: number;
  href?: string;
};

export const TESTIMONIALS: Testimonial[] = [];
export const CUSTOMER_LOGOS: CustomerLogo[] = [];
