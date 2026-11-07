"""Append real notification verification to an existing business test action."""
from .core import identifier, require
from .business import Messages


class NotificationHook:
    def __init__(self, api, recipient, notification_type, verify_ui, *, category=None):
        self.messages, self.recipient = Messages(api), recipient
        self.notification_type, self.verify_ui, self.category = notification_type, verify_ui, category
        self.baseline = None

    def before_business(self):
        self.baseline = {identifier(row.get("inboxId")) for row in
                         self.messages.notifications(self.recipient, self.category)}

    def after_business(self, business_id, assert_business_success):
        require(self.baseline is not None, "Capture notification baseline before business mutation")
        # This callback must query actual final business state, not inspect a toast.
        require(assert_business_success() is True, "Business has not reached required final state")
        detail = self.messages.notification_after(self.recipient, self.baseline, business_id,
                                                   self.notification_type, category=self.category)
        self.verify_ui(detail)  # Receiver UI detail/target/back/reentry assertions.
        return detail


def existing_business_with_notification(action, hook, *, business_id, assert_business_success, cleanup):
    """Single business mutation, then notification, then cleanup even on failure.

    action/cleanup reuse the original test functions; no new publication/order.
    Capture/restore callbacks belong to the current run and must verify cleanup.
    """
    hook.before_business()
    try:
        result = action()
        target = business_id(result)
        hook.after_business(target, lambda: assert_business_success(result))
        return result
    finally:
        cleanup()
