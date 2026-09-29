"""Publishing scheduled posts (T7.3; F-13, FR-PUB-05, FR-PUB-06, FR-PUB-11, FR-AUT-18).

The publish jobs' work (jobs/tasks/publishing.py stays thin):
- ``claims``: the dispatcher's claim of due targets and the sweeper's repairs (TR-JOB-03);
- ``publish``: publish_target (quota, containers), poll_container (processing, publish, the
  media item and automation links, the post's status, notifications) and post_first_comment;
- ``projection``: the ``scheduled_post.updated`` payload and the status rule.

Nothing here opens ``tenant_bypass_scope``: the jobs do, for the cross-workspace claims only.
"""
