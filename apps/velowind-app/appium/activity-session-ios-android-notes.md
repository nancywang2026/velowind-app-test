# Activity Session Appium Notes

## Scope

These notes track platform differences for the activity session management case:

1. Open My Activity.
2. Switch to Published.
3. Enable delisted activities.
4. Open the approved activity overflow menu.
5. Enter Manage Sessions.
6. Create a new session and submit successfully.

## Android

- The approved activity overflow button can be tapped using the right side of the top approved card. Android exposes `通过` as small text nodes, so filtering by badge bounds is usually stable.
- The session date picker exposes Android picker wheel ids such as `activity-session-create-deadline-picker-day-wheel`. The current implementation adjusts only the day wheel for relative test dates, then taps the bottom-right confirm area.
- Android Chinese input is more reliable through clipboard paste plus keycode `279` than direct `send_keys`; direct input previously produced duplicated or partial text.
- The location drawer may stay open after selecting a result. The script verifies that the form has the selected location after dismissing the drawer.
- For location results, the second visible result should be selected. On Android, tapping text nodes alone may not trigger row selection; the fallback taps the second row title area.

## iOS Real Device

- iOS page source can expose large ancestor/container elements whose `name` or `label` contains all visible text, including `通过`. Do not use those containers as status badges.
- For the approved activity overflow menu, filter `通过` candidates by small badge bounds before calculating the y-coordinate. Full-screen or large list container elements must be ignored.
- The iOS screen rect in WDA uses point coordinates, for example `402x874`, while screenshots are rendered at device pixel scale. Use Appium/WDA element rects or ratios based on `get_window_rect()`, not screenshot pixel dimensions.
- Some visual `...` overflow buttons are not exposed as direct text nodes in iOS XML. The safer fallback is to tap the right side of the approved card at the filtered `通过` badge y-coordinate.
- iOS page source may expose a large form/page container whose label contains `报名截止时间`, `开始时间`, and `结束时间`. Do not tap the center of that container. Use iOS-specific form coordinates for the three date fields.
- On iOS, the session date fields respond more reliably when tapping the calendar icon area instead of the visible date text. On a `402x874` WDA rect, use about `(177,268)` for signup deadline, `(177,348)` for start time, and `(370,348)` for end time.
- iOS `mobile: dragGesture` is not implemented by XCUITest in this environment; use `mobile: swipe` fallback for list scrolling.

## Date Control Handling

- Android session date fields open a custom picker that exposes Android wheel ids. The current stable path is to tap the field, adjust the day wheel for the relative target date, and tap the bottom-right confirm area.
- iOS session date fields are not exposed as `XCUIElementTypeTextField`; they appear as nested `XCUIElementTypeOther` containers with visible `StaticText` children such as `6月30日 10:00`.
- For iOS, do not consider a date field selected merely because a tap command succeeded. The tap must be followed by XML containing `XCUIElementTypePickerWheel`; otherwise try the next click strategy.
- iOS click strategy order for session dates should be: small field container `element.click()`, then W3C touch tap at the known field/icon point, then verified picker handling. Plain `mobile: tap` has not reliably triggered this control on the real device.
- If the iOS field container click does not open the picker, try several distinct points inside that field rectangle: right calendar/icon area, date value center, field center, and left value area. Each point still requires picker visibility before continuing.
- After opening the create-session form, avoid fixed "scroll down three times" behavior. If the top fields `场次展示文案`, `报名截止时间`, and `活动名额` are already visible, start filling immediately.

## Shared Guardrails

- Do not start filling the location search until the actual `搜索地点` drawer is visible. A generic input field with `input-type="16385"` is not enough to prove the location drawer opened.
- Do not treat seeing the draft title on the create form as success. The case passes only after submit exposes a success signal or returns to session management.
- If home recovery fails but the app is already on `我的`, retry the current-page My Activity navigation before failing.
