# iOS Search Note Case Performance Design

## Goal

Reduce the real-device execution time of
`test_user_can_search_open_and_interact_with_note` by limiting it to search and
detail-reading coverage. Move comment submission into an independent case that
opens a note directly from the home feed. Move like and favorite interactions
into another independent home-feed case. All three cases must finish without a
`logged_in_session` teardown timeout.

The target is a stable runtime near or below 90 seconds on the currently
configured iPhone. Device and network variance may affect the exact duration.

## Current Evidence

The recorded run took about 176 seconds. Its largest body steps were:

- opening the first result: about 27 seconds;
- liking the note: about 33 seconds;
- favoriting the note: about 34 seconds;
- submitting a comment: about 30 seconds.

All business steps passed. The final failure occurred in the centralized
`logged_in_session` teardown with `Home feed did not become ready`.

The final screenshot shows the note-detail back button centered near 5% of the
screen width. The shared recovery helper taps at 10% width, outside this button
on the note-detail layout, so the page does not unwind before the home-feed
wait.

## Design

### Case scope

Keep these behaviors in `test_ios_search_note.py`:

1. prepare the home session;
2. open note search;
3. search for the configured keyword;
4. open the first result;
5. verify that detail title and body are exposed.

Comment out the like, favorite, and comment calls and the like/favorite
assertions as requested. The commented lines remain visible in the search case
so the moved coverage is explicit.

### Independent comment case

Add a separate full-regression case for comment submission. Place it in
`tests/message/test_ios_home_note_interactions.py`, shared with the
like/favorite case. It must:

1. prepare the home session;
2. wait for the home note feed;
3. open the first eligible note card directly from the home feed;
4. verify that the note detail is visible;
5. submit the configured automation comment;
6. verify success through comment echo or a comment-count increase.

The comment case must not enter search. Keeping it independent makes failures
attributable to the home-feed/detail/comment flow and prevents comment latency
from inflating the search case.

### Independent like and favorite case

Add one separate full-regression case that covers both like and favorite. It
must live in the same home-note-interactions test file as the comment case and:

1. prepare the home session;
2. wait for the home note feed;
3. open the second eligible note card directly from the home feed;
4. verify that the note detail is visible;
5. tap like and verify its state or count changes;
6. tap favorite and verify its state or count changes.

This case must not enter search or submit a comment. Keeping both lightweight
bottom actions together avoids an extra driver setup while separating their
latency and failures from search and comment coverage.

The shared home-feed card opener must accept a one-based visible-card ordinal.
The comment case passes `1` and the interaction case passes `2`. It must ignore
navigation containers, duplicated accessibility ancestors, and non-card rows.

The shared test file owns only lightweight constants and a helper that opens a
home-feed card by ordinal and verifies note-detail visibility. Each test remains
independent: pytest setup and centralized teardown run around each test, so a
comment failure cannot skip or contaminate the like/favorite test.

### Search-result opening

Use the existing search-specific `open_first_note_search_result` helper instead
of the generic `tap_first_note_card` scan. The helper targets search-result
structure and performs one condition-based detail wait, avoiding repeated
generic card discovery and duplicate detail checks in the test.

### Teardown recovery

Change the shared top-left recovery tap from 10% to 5% of screen width while
keeping the current vertical position. This point hits both the note-detail
back control and the previously observed My Activities back region. Continue
to verify home visibility after the tap and retain `safe_back` as fallback.

No business case will contain its own return-to-home cleanup.

### Remaining performance work

After removing like, favorite, and comment from the search case and switching
to the search-specific opener, measure a fresh real-device run. Measure the new
comment case and the combined like/favorite case separately. Do not blindly
shorten timeouts. If any case still exceeds the target, profile only its
confirmed slow selector path.

## Error Handling

- Search or detail readiness still fails with the existing explicit assertions.
- The independent comment case requires visible echo or a comment-count
  increase.
- The independent interaction case requires both like and favorite state or
  count changes.
- Teardown must only report success after the home page is actually detected.
- System back remains a fallback when the coordinate tap does not navigate.

## Verification

1. Add or update unit tests for the 5% top-left coordinate, search-specific
   opener delegation, and independent comment-case flow.
2. Run the relevant session, home-feed, and message-detail helper suites.
3. Run `test_user_can_search_open_and_interact_with_note` on the real device.
4. Run the independent home-feed comment case on the real device.
5. Run the independent home-feed like/favorite case on the real device.
6. Confirm all three case bodies pass, all centralized teardowns complete, and
   record their individual runtimes.
