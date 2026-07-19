# iOS Activity Session Date Picker Design

## Context

The Appium add-session case already passes on Android but fails on an iOS real device while filling activity session datetime fields. Logs show the tap opens an iOS React Native custom date panel, but the automation only recognizes native `XCUIElementTypePickerWheel` pickers. The script then keeps tapping the same field, never writes the selected value, and the test eventually fails while filling `报名截止时间`.

## Goal

Make `test_user_can_add_activity_session_from_my_approved_activity` pass on the iOS real device without changing app business code or Android automation behavior.

## Scope

- Change only Appium automation code and its tests.
- Keep Android datetime writing on the existing Android path.
- Gate the new behavior strictly behind iOS platform detection.
- Handle the custom iOS datetime panel used by the session form.

## Design

Add an iOS-only custom datetime picker handler in `velowind_appium/modules/activity_sessions.py`.

The handler will:

1. Recognize both native iOS picker wheels and the observed custom picker panel.
2. Detect the custom panel using stable visible tokens: `已选择时间`, `取消`, `确认`, `月`, `日`, and `时`.
3. Parse the currently selected value from text such as `7月18日 22点`.
4. Adjust month, day, and hour on iOS using the visible picker panel.
5. Confirm the panel after the target value is selected.
6. Re-read page source after each meaningful action so the test waits for UI state changes instead of relying on blind fixed sleeps.

`_write_session_datetime_value()` will route as follows:

- iOS driver: use the new iOS custom picker writer when the iOS picker panel is visible.
- Android driver: keep using the existing Android custom picker writer.
- Other text input cases: keep the existing active text field fallback.

## Android Isolation

The implementation must call iOS-specific helpers only when `_is_ios_driver(driver)` is true. Android tests should prove that Android drivers do not enter the iOS writer or iOS picker path.

## Tests

Add focused unit coverage for:

- Custom iOS picker visibility detection.
- Current selected value parsing from iOS picker source.
- iOS routing from `_write_session_datetime_value()`.
- Android routing remaining on the existing Android path.

Run the related existing Android automation unit tests to guard against behavioral drift.

## Verification

Verification is complete only when:

1. The new focused unit tests pass.
2. Existing activity session unit tests pass.
3. The target iOS real-device Appium test passes with pytest exit code 0.
4. The final diff confirms no app business code changes and no unintended Android logic changes.
