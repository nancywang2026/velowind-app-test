"""Concrete dev API journeys. Run explicitly; reports never contain credentials.

API assertions are reported separately from native UI verification. Existing
business publications must use hooks.py; this runner never republishes them.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import time
import uuid
from urllib.request import ProxyHandler, build_opener

from .business import Messages, ROOT
from .core import API, ApiFailure, Blocked, NoRedirect, identifier, require, segment, wait


class LiveRun:
    def __init__(self, accounts_file, output, *, api=None):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex
        self.api = api or API('https://dev-api.velowind.com', opener=build_opener(ProxyHandler({}), NoRedirect()))
        self.messages = Messages(self.api)
        self.report = {'run_id': self.run_id, 'origin': self.api.origin, 'cases': [],
                       'resources': [], 'native_ui': 'not-verified'}
        try:
            source = json.loads(Path(accounts_file).read_text())['accounts']
            require(len({str(source[r]['user_id']) for r in 'abc'}) == 3, 'Distinct accounts required')
            self.actors = {r: self.api.login(source[r]['username'], source[r]['password'],
                          expected_id=source[r]['user_id'], name=source[r]['name']) for r in 'abc'}
            self._secrets = [source[r]['password'] for r in 'abc'] + [x.token for x in self.actors.values()]
        except (OSError, ValueError, KeyError, TypeError):
            raise Blocked('Cannot load grouped A/B/C account file') from None
        self.save()

    def save(self):
        path = self.output / 'live-results.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps({**self.report, 'api': self.api.journal}, ensure_ascii=False, indent=2))
        tmp.replace(path)
        from .allure_report import export_record
        export_record(self.report, path, self.output / 'allure-results')

    def reject_owner_operation(self, actor, method, path, body=None):
        try:
            self.api.request(actor, method, path, body=body)
        except ApiFailure as exc:
            if exc.code == 17000106 and exc.message_key == 'message.mobile-center.capability-unavailable':
                raise Blocked('Member management API capability unavailable; owner authorization not proven') from None
            require(exc.status == 400 and exc.code == 17000075
                    and exc.message_key == 'message.chatroom.owner_required',
                    'Operation failed for a reason other than owner authorization')
        else:
            raise AssertionError('Non-owner operation unexpectedly succeeded')

    @contextmanager
    def case(self, name):
        from .case_descriptions import description
        row = {'name': name, 'status': 'running', 'verification': 'API',
               'start': time.time_ns() // 1_000_000}
        if description(name):
            row['test_description'] = description(name)
        self.report['cases'].append(row)
        self.save()
        start = time.monotonic()
        try:
            yield row
            row['status'] = 'passed'
        except Exception as exc:
            row['status'] = 'blocked' if isinstance(exc, Blocked) else 'failed'
            row['error'] = type(exc).__name__
            if isinstance(exc, ApiFailure):
                row.update(http_status=exc.status, business_code=exc.code, message_key=exc.message_key)
            elif isinstance(exc, (AssertionError, Blocked)):
                reason = str(exc).split('<?xml',1)[0]
                for secret in getattr(self,'_secrets',[]):
                    if secret: reason=reason.replace(secret,'<redacted>')
                row['reason'] = reason[:500]
            raise
        finally:
            row['seconds'] = round(time.monotonic()-start, 3)
            row['stop'] = time.time_ns() // 1_000_000
            capture = getattr(self, 'capture_evidence', None)
            if capture:
                try:
                    row.setdefault('screenshots', []).extend(capture(name, row['verification']))
                except Exception as exc:
                    row['screenshot_error'] = type(exc).__name__
            self.save()

    def groups(self, observe=None, *, images=False):
        """One unique owner-C group; A accepts, B rejects then accepts a fresh invite."""
        owner, a, b = (self.actors[r] for r in ('c', 'a', 'b'))
        name = '消息' + self.run_id[:8]
        resource = {'kind': 'chatroom', 'name': name, 'status': 'creation-pending'}
        self.report['resources'].append(resource)
        group_id = None
        try:
            with self.case('group.create-and-member-list'):
                group = self.messages.create_group(owner, name)
                group_id = identifier(group['chatroomId'])
                resource.update(id=group_id, status='active'); self.save()
                detail = self.messages.group(owner, group_id)
                require(detail['memberRole'] == 'OWNER' and detail['memberCount'] == 1, 'Wrong initial group membership')
                require({str(x['memberUserId']) for x in self.messages.members(owner, group_id)} == {owner.user_id}, 'Initial members mismatch')
            if observe:
                with self.case('group.native-list-and-detail') as row:
                    row['verification'] = 'native-UI'
                    observe(name, group_id)
            path = ROOT + '/chatrooms/' + segment(group_id)
            with self.case('group.invite-accept-reject'):
                batch = self.api.request(owner, 'POST', path+'/invitations', body={'inviteeUserIds': [a.user_id, b.user_id]})
                items = batch['items']
                require(len(items) == 2, 'Invitation batch incomplete')
                by_user = {str(x['inviteeUserId']): x for x in items}
                for actor, action, expected in ((a, 'accept', 'ACCEPTED'), (b, 'reject', 'REJECTED')):
                    inv = by_user[actor.user_id]
                    require(inv['status'] == 'PENDING_ACCEPTANCE', 'Unexpected initial invitation status')
                    ipath = ROOT+'/chatroom-invitations/'+segment(inv['invitationId'])
                    self.api.request(actor, 'POST', ipath+'/'+action)
                    result = self.api.request(actor, 'GET', ipath)
                    require(result['status'] == expected, 'Invitation terminal state mismatch')
                require(self.messages.group(owner, group_id)['memberCount'] == 2, 'Rejected invitation added a member')
            with self.case('group.reinvite-and-search-members'):
                batch = self.api.request(owner, 'POST', path+'/invitations', body={'inviteeUserIds': [b.user_id]})
                inv = batch['items'][0]
                self.api.request(b, 'POST', ROOT+'/chatroom-invitations/'+segment(inv['invitationId'])+'/accept')
                members = self.messages.members(owner, group_id)
                require({str(x['memberUserId']) for x in members} == {x.user_id for x in (owner,a,b)}, 'Accepted membership mismatch')
                matches = self.messages.members(owner, group_id, keyword=a.name)
                require(any(str(x['memberUserId']) == a.user_id for x in matches), 'Member search did not return current member')
            with self.case('group.pin-mute-per-user-persistence'):
                for flag in ('pin', 'mute'):
                    field = 'pinned' if flag == 'pin' else 'muted'
                    self.api.request(a, 'POST', path+'/'+flag)
                    require(self.messages.group(a, group_id)[field] is True, 'Group preference not persisted')
                    require(self.messages.group(owner, group_id)[field] is False, 'Group preference leaked to owner')
                    self.api.request(a, 'DELETE', path+'/'+flag)
                    require(self.messages.group(a, group_id)[field] is False, 'Group preference not reset')
            with self.case('group.rename-and-announcement'):
                renamed = name+'改'
                self.api.request(owner, 'PUT', path+'/name', body={'name': renamed})
                require(self.messages.group(a, group_id)['chatroomName'] == renamed, 'Group rename not visible to member')
                current = self.api.request(owner, 'GET', path+'/announcement')
                version = current['version']
                self.api.request(owner, 'PUT', path+'/announcement', body={'expectedVersion': version, 'content': '自动化公告 '+self.run_id[:8]})
                after = self.api.request(a, 'GET', path+'/announcement')
                require(after['version'] == version+1 and after['publisherUserId'] == owner.user_id, 'Announcement publication mismatch')
            for label,method,suffix,body in (
                    ('rename','PUT','/name',{'name':name+'越权'}),
                    ('announcement','PUT','/announcement',{'expectedVersion':after['version'],'content':'越权公告'}),
                    ('dissolve','POST','/dissolve',None)):
                try:
                    with self.case('group.member-cannot-'+label):
                        self.reject_owner_operation(a,method,path+suffix,body)
                except Blocked:
                    pass  # Record missing capability and continue independent assertions.
            with self.case('group.rejected-owner-operations-preserve-state'):
                require(self.messages.group(owner,group_id)['chatroomStatus']=='ACTIVE','Member dissolved current group')
                require(self.messages.group(a,group_id)['chatroomName']==renamed,'Rejected rename changed group name')
                require(self.api.request(a,'GET',path+'/announcement')['version']==after['version'],'Rejected edit changed announcement')
            with self.case('group.text-order-and-older-pagination'):
                sent = [self.messages.send(owner, group_id, f'{name}消息{i}', group=True) for i in range(5)]
                sent.extend(self.messages.send(sender,group_id,name+'回复'+role,group=True)
                            for role,sender in (('a',a),('b',b)))
                ids = [str(x['messageId']) for x in sent]
                history = self.messages.history(a, group_id, group=True, expected_ids=ids, page_size=2, direction='older')
                actual = sorted((x for k,x in history.items() if k in ids), key=lambda x:(x.get('createdAtEpochMillis',x.get('createdAt')),str(x['messageId'])))
                require([str(x['messageId']) for x in actual] == ids, 'Message order mismatch')
                require({x['senderUserId'] for x in actual}=={x.user_id for x in (owner,a,b)},'Bidirectional group senders mismatch')
                resource['message_ids'] = ids
            if images:
                from .media import upload_group_image, assert_media_bytes
                with self.case('group.image-bidirectional-full-bytes'):
                    for sender, recipient in ((owner,a),(a,owner)):
                        asset_id, png = upload_group_image(self,sender,group_id)
                        message = self.messages.send(sender,group_id,'',group=True,image_ids=[asset_id])
                        message_id = str(message['messageId'])
                        history = self.messages.history(recipient,group_id,group=True,expected_ids=[message_id],direction='older')
                        assert_media_bytes(self,history[message_id],asset_id,png)
                        # Refetch history to obtain a new signed URL and verify reentry access.
                        again = self.messages.history(recipient,group_id,group=True,expected_ids=[message_id],direction='older')
                        assert_media_bytes(self,again[message_id],asset_id,png)
            with self.case('group.read-and-own-history-clear'):
                self.api.request(a, 'POST', path+'/read')
                require(self.messages.group(a, group_id)['unreadCount'] == 0, 'Group unread not reset')
                self.api.request(a, 'POST', path+'/clear')
                mine = self.messages.history(a, group_id, group=True, direction='older')
                require(not set(ids).intersection(mine), 'Own cleared messages still visible')
                self.messages.history(b, group_id, group=True, expected_ids=ids, direction='older')
            with self.case('group.remove-member-and-exit'):
                result = self.api.request(owner, 'DELETE', path+'/members/'+segment(a.user_id))
                require(result['memberStatus'] == 'REMOVED_BY_OWNER', 'Removal state mismatch')
                self.api.request(b, 'POST', path+'/exit')
                require(self.messages.group(owner, group_id)['memberCount'] == 1, 'Member removal/exit count mismatch')
        finally:
            # Unknown create outcome is reconciled by this run's unique name; never retry create.
            try:
                if not group_id:
                    rows = self.api.request(owner,'GET',ROOT+'/chatrooms')['items']
                    matches = [x for x in rows if x.get('chatroomName') == name]
                    require(len(matches) <= 1, 'Ambiguous create reconciliation')
                    group_id = str(matches[0]['chatroomId']) if matches else None
                if group_id:
                    path = ROOT+'/chatrooms/'+segment(group_id)
                    if self.messages.group(owner,group_id)['chatroomStatus'] == 'ACTIVE':
                        self.api.request(owner,'POST',path+'/dissolve')
                    require(self.messages.group(owner,group_id)['chatroomStatus'] == 'DISSOLVED_READ_ONLY','Dissolution unconfirmed')
                    resource.update(id=group_id,status='dissolved-read-only', residual='Read-only group history retained by product')
                else: resource['status']='not-created'
            except Exception as exc:
                resource.update(status='cleanup-pending',error=type(exc).__name__)
            self.save()

    def private_text(self, observe=None):
        sender, recipient = self.actors['c'], self.actors['a']
        sent = []
        with self.case('private.unread-baseline'):
            require(self.messages.unread(recipient,sender) == 0, 'Recipient has pre-existing unread; preserve existing messages')
        try:
            with self.case('private.send-order-unread'):
                for i in range(3):
                    sent.append(self.messages.send(sender, recipient.user_id, '消息自动化'+self.run_id[:8]+'-'+str(i)))
                    self.report['resources'].append({'kind':'private-message','id':str(sent[-1]['messageId']),
                         'status':'retained','reason':'No destructive clearing of existing conversation'})
                    self.save()
                wait(lambda:self.messages.unread(recipient,sender),lambda x:x==3)
                history=self.messages.history(recipient,sender.user_id,expected_ids=[str(x['messageId']) for x in sent],direction='older')
                for message in sent:
                    incoming=history[str(message['messageId'])]
                    require(incoming['content']==message['content'] and incoming['direction']=='INBOUND','Recipient message mismatch')
            if observe:
                with self.case('private.native-sent-state-and-latest') as row:
                    row['verification']='native-UI';observe(sent,False)
            with self.case('private.read-and-counter'):
                data=self.api.request(recipient,'POST',ROOT+'/private-conversations/'+segment(sender.user_id)+'/read')
                require(data['markedReadCount']==3 and data['conversationUnreadCount']==0,'Read count mismatch')
                require(self.messages.unread(recipient,sender)==0,'Read state not persisted')
            if observe:
                with self.case('private.native-read-icon') as row:
                    row['verification']='native-UI';observe(sent,True)
        finally:
            self.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accounts',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--suite',choices=('groups','private','all'),default='groups')
    parser.add_argument('--images',action='store_true',help='Upload current-run group images and verify exact recipient bytes')
    args=parser.parse_args()
    run=LiveRun(args.accounts,args.output)
    for name in (('groups','private') if args.suite=='all' else (args.suite,)):
        try:
            if name=='groups':run.groups(images=args.images)
            else:run.private_text()
        except Exception: pass  # Exact sanitized failures are persisted; continue independent suite.
    run.save()
    statuses=[x['status'] for x in run.report['cases']]
    pending=any(x['status']=='cleanup-pending' for x in run.report['resources'])
    print(json.dumps({'cases':len(statuses),'passed':statuses.count('passed'),'failed':statuses.count('failed'),
                      'blocked':statuses.count('blocked'),'cleanup_pending':pending,'native_ui':'not-verified'}))
    return 1 if pending or any(x!='passed' for x in statuses) else 0


if __name__=='__main__':
    raise SystemExit(main())
