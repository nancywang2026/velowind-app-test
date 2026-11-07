"""Adapter from existing publication helpers to a real NotificationHook."""
from .core import identifier


class PublicationObserver:
    def __init__(self, notification_hook, resolve_current_id, assert_published):
        self.notification_hook = notification_hook
        self.resolve_current_id = resolve_current_id
        self.assert_published = assert_published

    def before_business(self):
        self.notification_hook.before_business()

    def after_publication(self, driver, config, draft, submission_signal):
        # Resolver must identify the current run's entity, never "latest order".
        business_id = identifier(self.resolve_current_id(driver, config, draft))
        return self.notification_hook.after_business(business_id,
            lambda:self.assert_published(business_id, driver, config, draft))


class PostPublicationObserver:
    """Concrete observer for the existing note publisher, with scoped admin A.

    Capture existing IDs before the single UI publish. Only a new matching note
    created during this operation can be approved/rejected; no old data lookup.
    """
    def __init__(self,api,author,admin,verify_ui,*,outcome='approve'):
        from .hooks import NotificationHook
        from .core import require
        require(outcome in ('approve','reject'),'Invalid post moderation outcome')
        self.api,self.author,self.admin,self.outcome=api,author,admin,outcome
        kind='POST_AUDIT_APPROVED' if outcome=='approve' else 'POST_AUDIT_REJECTED'
        self.hook=NotificationHook(api,author,kind,verify_ui)
        self.existing_ids=None
        self.post_id=None

    def mine(self):
        return self.api.pages(self.author,'/api/v1/mobile/posts/mine',id_key='postId',params={'status':'ALL'})

    def before_business(self):
        import time
        self.started_at=int(time.time()*1000)
        self.existing_ids={str(x['postId']) for x in self.mine()}
        self.hook.before_business()

    def after_publication(self,driver,config,draft,submission_signal):
        from .core import Blocked,require,segment,wait
        require(self.existing_ids is not None,'Capture publication baseline first')
        publication=getattr(driver,'_api_note_publication',None)
        title=draft.title
        known_id=None
        if publication:
            require(publication.get('requested_title')==draft.title,'Publication scope does not match requested draft')
            title=publication['published_title']
            known_id=publication.get('post_id')
        def candidates():
            return [x for x in self.mine() if str(x['postId']) not in self.existing_ids
                    and x.get('title')==title and (known_id is None or str(x['postId'])==str(known_id))
                    and x.get('createdAtEpochMillis',0)>=self.started_at-5000]
        matches=wait(candidates,bool,timeout=60)
        require(len(matches)==1,'Ambiguous current publication; moderation prohibited')
        self.post_id=str(matches[0]['postId'])
        path='/api/v1/mobile/posts/mine/'+segment(self.post_id)
        def current():
            value=self.api.request(self.author,'GET',path)
            require(str(value.get('postId'))==self.post_id and value.get('title')==title
                    and (value.get('content') or '').startswith(draft.body),'Current note content/identity changed')
            return value
        note=wait(current,lambda x:x.get('publishStatus') in {'PENDING_MANUAL_AUDIT','PUBLISHED','REJECTED'},timeout=60)
        expected='PUBLISHED' if self.outcome=='approve' else 'REJECTED'
        if note['publishStatus']!=expected:
            if note['publishStatus']!='PENDING_MANUAL_AUDIT':
                raise Blocked('Current note did not enter manual moderation for requested outcome')
            revision=note.get('revisionNo')
            require(type(revision) is int and revision>0,'Missing current note revision')
            self.api.request(self.admin,'POST','/api/v1/admin/posts/'+segment(self.post_id)
                +'/revisions/'+str(revision)+'/'+self.outcome,
                body={'reason':'自动化测试：本轮新建笔记审核拒绝'} if self.outcome=='reject' else None)
        note=wait(current,lambda x:x.get('publishStatus')==expected,timeout=60)
        if expected=='PUBLISHED':
            public=self.api.request(self.author,'GET','/api/v1/mobile/posts/'+segment(self.post_id))
            require(str(public.get('authorUserId'))==self.author.user_id,'Published note owner mismatch')
        return self.hook.after_business(self.post_id,lambda:current().get('publishStatus')==expected)
