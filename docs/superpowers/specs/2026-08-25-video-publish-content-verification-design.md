# Video Publish Content Verification Design

## Goal

Add an automated verification flow for published videos so the test can confirm that the content users see after publishing matches the uploaded source video.

This design targets content equivalence, not byte-for-byte file identity.

## Non-Goals

- Do not change the existing image comparison logic.
- Do not modify `image_validation.py`.
- Do not introduce a shared media comparator that would couple image and video behavior.

## Design

- Add a new `video_validation.py` module that owns all video comparison logic.
- Keep the current image comparison flow untouched and continue using it only for image publish cases.
- Add a video-specific publish helper, separate from the existing image publish helper, so the video path can evolve independently.
- Reuse existing publish-note test data and `media_type == video` selection, but route those cases through the new video validator.
- Use a decode-based comparison instead of raw file hashing, because publishing may transcode the asset.

### Comparison strategy

- Check metadata first: duration, resolution, rotation, and frame rate.
- Decode both videos and sample frames at a fixed cadence or by scene changes.
- Compare sampled frames with a perceptual metric such as pHash or SSIM.
- Extract audio separately and compare its fingerprint or normalized feature similarity.
- Aggregate the result into a single comparison object with sub-scores and a clear failure reason.

### Suggested API

- `compare_videos_for_publish(source_path, actual_path) -> VideoComparisonResult`
- `VideoComparisonResult` should include:
  - `is_valid`
  - `duration_delta`
  - `frame_similarity`
  - `audio_similarity`
  - `resolution_match`
  - `reason`

### Publish flow

- Run the existing publish flow for a video draft.
- Capture the published media URL or downloadable asset reference from the success result or backend response.
- Download the published video to a temp path.
- Run the video comparator against the original source file.
- Attach the comparison summary to the test report.

## Validation

- Unit tests for metadata checks, frame sampling, audio comparison, and failure reasons.
- Integration tests for:
  - an unchanged video
  - a cropped or re-encoded video
  - a video with altered audio
- Existing image publish tests remain unchanged and should continue to pass.

