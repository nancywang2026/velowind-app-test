# Zhangjiajie Activity Publish Cross-Platform Design

## Goal

Create an Appium publish-activity test case that uses the Zhangjiajie 2-day/1-night activity as the source data and can run on both iOS and Android.

## Architecture

The existing activity publish workflow already centralizes the UI automation in `velowind_appium.modules.activity`. The test should stay thin: build an `ActivityDraft`, prepare a logged-in home session, publish the activity, and assert the review/success signal.

The fixture data should be the single source of truth. Fields that are submitted by the helper must come from `tests/activity/testdata/publish_activity.yaml`, including contact, participant, and fee values, so Android and iOS cannot drift.

## Data Requirements

The first YAML activity case represents `张家界大环线2天1晚`. It includes title, type, province, city, album, description, two itinerary segments, meeting point, contact name, contact phone, max participants, fee, and advanced metadata for duration, mileage, altitude, elevation, tags, season, and risk.

## Test Requirements

Use a platform-neutral activity publish test file under `tests/activity/`. The iOS suite and Android activity publish suite should point to the same test file. Android local publish mode should run the activity publish suite when requested for this activity case.

## Error Handling

If a required field placeholder remains after filling, the existing helper fails the test. If publish does not reach success/review state, the test fails with the last visible page source excerpt and captures Appium debug artifacts through the existing pytest hook.

## Verification

Run focused unit tests for activity draft/data behavior first, then run the Android activity publish suite on the emulator through the repository's local Appium script.
