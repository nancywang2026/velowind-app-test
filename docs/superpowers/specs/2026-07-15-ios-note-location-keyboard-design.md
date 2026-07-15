# iOS Note Location Keyboard Design

## Problem

After the note body and topics are entered, `_dismiss_editor_keyboard()` hides the
keyboard and then unconditionally taps at 90% of the screen width and 18% of the
screen height. On the note form, that point overlaps the selected-image thumbnail
row. The tap reopens the image cropper, so the following location-selection code
runs behind the cropper and fails with `Unable to select a note location option`.

## Design

The note flow will dismiss the editor keyboard by clicking the visible keyboard
`完成` action first. If that action is unavailable, it may use Appium's native
keyboard-dismiss APIs, but it must not use a coordinate fallback in the image
thumbnail region.

Before opening the location picker, the flow will detect an unexpectedly visible
cropper and stop with a state-specific assertion. Normal location picker and
location result selection logic remains unchanged.

## Verification

Helper tests will verify that:

- the visible `完成` action is preferred;
- successful keyboard dismissal does not produce a coordinate tap;
- an unexpectedly visible cropper is rejected before location selection;
- the existing location-opening path still selects a location.

The unrelated pre-existing failure in
`test_clear_existing_note_images_taps_scoped_remove_buttons_until_gone` is outside
this change and is excluded from the requested verification scope.
