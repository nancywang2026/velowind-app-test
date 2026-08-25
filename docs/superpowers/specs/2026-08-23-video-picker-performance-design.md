# Video Picker Performance Design

## Goal

Reduce the time spent selecting the first video in the iOS publish-note flow while preserving the required 10-second maximum preview wait and direct selection from the Videos view.

## Design

- Keep the existing direct Videos filter path; never navigate to the Collections/精选集 view.
- Replace the unconditional 10-second sleep after selecting a video with a bounded readiness wait. Continue immediately when the preview page exposes the confirmation action; otherwise wait up to 10 seconds, then use the existing confirmation fallback.
- Avoid repeated full accessibility snapshots while waiting. Poll the small set of confirmation indicators first, and only read page source when the fast element checks do not resolve the state.
- Preserve the existing fallback behavior and failure diagnostics when no video or confirmation action is available.

## Validation

- Unit tests cover early confirmation, the 10-second timeout fallback, and the direct Videos path.
- Existing image picker tests remain unchanged and pass.
- A real-device video publish run records picker profiling and Allure artifacts; the comparison focuses on `choose-video` and preview-confirm timings.
