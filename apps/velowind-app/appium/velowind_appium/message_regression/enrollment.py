"""Notifications appended to the existing signup case, using its one enrollment.

No old enrollment IDs or payment globals are accepted. Payment is optional and
must complete through the normal cashier plus the guarded mock payment client.
"""
from .business import Messages, ROOT
from .core import Blocked, identifier, require, segment, wait


class EnrollmentObserver:
    def __init__(self,api,actor,verify_ui,*,admin=None,payment_complete=None,ending='cancel'):
        require(ending in ('cancel','admin_cancel','reject'),'Invalid enrollment ending')
        self.api,self.actor,self.admin=api,actor,admin
        self.messages=Messages(api)
        self.verify_ui,self.payment_complete,self.ending=verify_ui,payment_complete,ending
        self.existing_ids=None;self.enrollment_id=None;self.notification_baseline=None
        self.cleanup_status='not-started'

    def mine(self):
        return self.api.pages(self.actor,'/api/v1/mobile/activity/enrollments/me',id_key='enrollmentId')

    def before_business(self):
        import time
        if self.ending in ('admin_cancel','reject') and self.admin is None:
            raise Blocked('Admin A session required before creating signup')
        self.started_at=int(time.time()*1000)
        self.existing_ids={str(x['enrollmentId']) for x in self.mine()}
        self.notification_baseline={str(x['inboxId']) for x in self.messages.notifications(self.actor)}

    def current(self):
        require(self.enrollment_id is not None,'Current signup has not been resolved')
        data=self.api.request(self.actor,'GET','/api/v1/mobile/activity/enrollments/'+segment(self.enrollment_id))
        require(str(data.get('enrollmentId'))==self.enrollment_id and str(data.get('operatorUserId'))==self.actor.user_id,
                'Current enrollment identity/owner mismatch')
        return data

    def notice(self,kind):
        detail=self.messages.notification_after(self.actor,self.notification_baseline,self.enrollment_id,kind)
        self.verify_ui(detail)
        return detail

    def after_signup(self,driver,config,snapshot):
        require(self.existing_ids is not None,'Capture signup baseline before submit')
        def candidates():
            return [x for x in self.mine() if str(x['enrollmentId']) not in self.existing_ids
                    and x.get('createdAtEpochMillis',0)>=self.started_at-5000]
        matches=wait(candidates,bool)
        require(len(matches)==1,'Multiple new signups; cannot select current business order')
        self.enrollment_id=identifier(matches[0]['enrollmentId'])
        order=self.current()
        if order.get('enrollmentStatus') in ('PENDING_PAYMENT','WAITING_PAYMENT'):
            if self.payment_complete is None:
                raise Blocked('Current paid signup requires normal confirm-payment and guarded mock completion')
            self.payment_complete(driver,config,self.enrollment_id,self.actor)
            order=wait(self.current,lambda x:x.get('enrollmentStatus') in ('CONFIRMED','PENDING_REVIEW'))
        if self.ending!='reject':
            require(order.get('enrollmentStatus')=='CONFIRMED','Signup is not confirmed; no success notification assertion')
            self.notice('ACTIVITY_ENROLLMENT_OWNER_CONFIRMED')
            session_id=identifier((order.get('sessionDetail') or {}).get('sessionId'))
            entry=self.api.request(self.actor,'GET',ROOT+'/activity-sessions/'+segment(session_id)+'/chatroom-entry')
            # Keep the current entry response for caller-specific UI navigation;
            # no alternate activity/session is selected for the group assertion.
            self.activity_group_entry=entry
            require(str(entry.get('sessionId'))==session_id,'Activity group entry belongs to another session')
            entry=wait(lambda:self.api.request(self.actor,'GET',ROOT+'/activity-sessions/'+segment(session_id)+'/chatroom-entry'),
                       lambda x:x.get('status') in ('READY','UNAVAILABLE'),timeout=60,interval=3)
            require(entry.get('status')=='READY' and entry.get('memberStatus')=='ACTIVE'
                    and entry.get('sendAllowed') is True,'Confirmed signup did not join its current activity group')
        self.finish_current()
        return self.current()

    def finish_current(self):
        order=self.current()
        status=order.get('enrollmentStatus')
        if self.ending=='reject':
            require(status=='PENDING_REVIEW','Only this run’s review-pending signup can be rejected')
            self.api.request(self.admin,'POST','/api/v1/admin/activity/enrollments/'+segment(self.enrollment_id)+'/reject',
                             body={'rejectReason':'自动化测试：本轮报名资料审核拒绝'})
            expected='REJECTED'
        else:
            require(status=='CONFIRMED','Only a confirmed current signup can be cancelled')
            path=('/api/v1/admin/activity/enrollments/' if self.ending=='admin_cancel' else '/api/v1/mobile/activity/enrollments/')
            self.api.request(self.admin if self.ending=='admin_cancel' else self.actor,'POST',path+segment(self.enrollment_id)+'/cancel')
            expected='CANCELED'
        terminal={'REJECTED'} if expected=='REJECTED' else {'CANCELED','REFUNDED','REFUND_FAILED'}
        order=wait(self.current,lambda x:x.get('enrollmentStatus') in terminal,timeout=120)
        if order.get('paymentStatus')=='SUCCEEDED':
            order=wait(self.current,lambda x:x.get('refundStatus') in ('SUCCEEDED','FAILED'),timeout=120)
            require(order.get('refundStatus')=='SUCCEEDED','Refund did not succeed; no refund-success notification assertion')
            require(bool(order.get('refundOrderId')),'Refund success has no actual refund order binding')
            kind=('ACTIVITY_ENROLLMENT_REVIEW_REJECT_REFUND_SUCCEEDED' if expected=='REJECTED'
                  else 'ACTIVITY_ENROLLMENT_ACTIVE_CANCEL_REFUND_SUCCEEDED')
        else:
            kind=('ACTIVITY_ENROLLMENT_REVIEW_REJECT_NO_REFUND' if expected=='REJECTED'
                  else 'ACTIVITY_ENROLLMENT_ACTIVE_CANCEL_NO_REFUND')
        self.notice(kind)
        self.cleanup_status='cancelled-or-rejected-and-notification-verified'

    def cleanup(self):
        """Cancel only the newly created signup, even if a notification failed."""
        if self.existing_ids is None:return {'status':'not-created'}
        if self.enrollment_id is None:
            matches=[x for x in self.mine() if str(x['enrollmentId']) not in self.existing_ids
                     and x.get('createdAtEpochMillis',0)>=self.started_at-5000]
            require(len(matches)<=1,'Ambiguous new signup cleanup; no old order will be cancelled')
            if not matches:return {'status':'no-current-signup-found'}
            self.enrollment_id=identifier(matches[0]['enrollmentId'])
        order=self.current()
        if order.get('enrollmentStatus') in ('PENDING_REVIEW','WAITING_PAYMENT','PENDING_PAYMENT','CONFIRMED'):
            self.api.request(self.actor,'POST','/api/v1/mobile/activity/enrollments/'+segment(self.enrollment_id)+'/cancel')
        order=wait(self.current,lambda x:x.get('enrollmentStatus') in {'CANCELED','REJECTED','REFUNDED','REFUND_FAILED','PAYMENT_TIMEOUT_CANCELED'},timeout=120)
        if order.get('paymentStatus')=='SUCCEEDED':
            require(order.get('refundStatus')=='SUCCEEDED','cleanup-pending: paid signup refund unconfirmed')
        self.cleanup_status='business-cancelled-or-rejected'
        return {'enrollment_id':self.enrollment_id,'status':self.cleanup_status,
                'enrollment_status':order.get('enrollmentStatus'),'refund_status':order.get('refundStatus')}
