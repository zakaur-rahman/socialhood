/**
 * A URL the API handed over for leaving the app (checkout, customer portal, Instagram's consent
 * page) must be a web page: never a javascript: or data: URL, which would run in this origin.
 */
export function webUrl(url: string): string {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Refusing to open a URL that isn't a web page.");
  }
  return parsed.href;
}

/**
 * Leaving for Dodo (F-15, FR-BIL-04) or Instagram (F-03). One object, so tests can replace the
 * navigation that jsdom doesn't implement.
 */
export const browser = {
  /** Checkout: the browser goes to Dodo and comes back to ?checkout=return. */
  assign(url: string): void {
    window.location.assign(webUrl(url));
  },
  /**
   * The customer portal opens in a new tab. The tab is opened during the click, before the portal
   * URL arrives, so popup blockers (Safari especially) allow it; it cannot reach back to this page.
   */
  openPending(): { go: (url: string) => void; cancel: () => void } {
    let tab: Window | null = null;
    try {
      tab = window.open("", "_blank");
      if (tab) tab.opener = null;
    } catch {
      tab = null;
    }
    return {
      go: (url) => {
        let target: string;
        try {
          target = webUrl(url);
        } catch (error) {
          if (tab && !tab.closed) tab.close(); // no blank tab left behind
          throw error;
        }
        if (tab && !tab.closed) tab.location.href = target;
        else window.location.assign(target);
      },
      cancel: () => {
        if (tab && !tab.closed) tab.close();
      },
    };
  },
};
