"""Analytics tools (FR-AGT-02, FR-AGT-04, FR-AGT-06, TR-AGT-05, TA.4; agent-architecture.html §6).

Every number comes from services/analytics, the same typed queries the UI uses; the model only
explains them. Results carry the age actually used, the time range and the sample size.

R1 (all read):
- post_performance(post_id, at_age): reach, views, likes, comments, shares, saves and engagement
  rate at the snapshot closest to the age (FR-ANL-01), or lifetime; the age used.
- compare_posts(post_id, baseline, at_age): the post against the baseline's median and mean per
  metric at the same age; previous N posts or a range, same format by default; fewer than 3
  comparable posts is "not enough history".
- top_posts(metric, range, n, at_age) / above_average_posts(metric, range, at_age).
- engagement_trend(range, bucket) / account_metrics(range): per day or week, where Instagram
  provides them (insights granted, 100+ followers for demographics).
- sentiment_distribution(scope) / sentiment_trend(range, bucket) / compare_sentiment(post_id,
  baseline): analysed against total, unanalysed reported.
- comment_topics(scope, sentiment, n): top topics with counts and example comments (TR-AI-11).
- lead_metrics(range, account): conversations with lead score ≥ 60 and first-response time.

Without the insights permission a tool returns what it has and a caveat ("insights aren't
granted"); a post younger than the requested age is compared at its current age, and says so.
"""

from __future__ import annotations
