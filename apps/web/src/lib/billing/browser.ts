/**
 * Leaving for Dodo (F-15, FR-BIL-04). One object, so tests can replace the navigation that jsdom
 * doesn't implement.
 */
export const browser = {
  /** Checkout: the browser goes to Dodo and comes back to ?checkout=return. */
  assign(url: string): void {
    window.location.assign(url);
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
        if (tab && !tab.closed) tab.location.href = url;
        else window.location.assign(url);
      },
      cancel: () => {
        if (tab && !tab.closed) tab.close();
      },
    };
  },
};
