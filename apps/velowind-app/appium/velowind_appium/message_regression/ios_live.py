"""Native assertions against an explicitly owned, existing Appium session.

Does not create or replace sessions. UI identity is checked before navigation.
Locators are based on 1.3.0 build 64 device XML, not fabricated test IDs.
"""
from __future__ import annotations
import argparse
import base64
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from xml.etree import ElementTree as ET

from .core import Blocked, require, wait
from .live import LiveRun


class OwnedIOS:
    def __init__(self, session_file):
        data=json.loads(Path(session_file).read_text())
        self.server=data['server']
        parsed=urlsplit(self.server)
        require(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port
                and parsed.path in ('','/') and not parsed.query and not parsed.fragment
                and not parsed.username and not parsed.password,'Local owned Appium server required')
        self.server=self.server.rstrip('/')
        self.session_id=data['session_id']
        require(bool(re.fullmatch(r'[A-Za-z0-9-]{1,80}',self.session_id)),'Invalid owned session ID')
        require(data.get('udid') and data.get('bundle_id'),'Owned device identity required')
        self.bundle_id=data['bundle_id']
        self.opener=build_opener(ProxyHandler({}))

    def call(self,path,method='GET',body=None):
        request=Request(self.server+'/session/'+self.session_id+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type':'application/json'},method=method)
        try:
            with self.opener.open(request,timeout=50) as response:data=json.load(response)
        except HTTPError as exc:
            exc.close()
            raise Blocked('Owned Appium session unavailable; do not replace another session') from None
        value=data.get('value')
        require(not(isinstance(value,dict) and value.get('error')),'Native Appium command failed')
        return value

    @staticmethod
    def text_predicate(text):
        value=text.replace('\\','\\\\').replace('"','\\"')
        return 'type == "XCUIElementTypeStaticText" AND name == "'+value+'"'

    def elements(self,value,using='-ios predicate string'):
        return self.call('/elements','POST',{'using':using,'value':value})

    def click(self,value,using='-ios predicate string'):
        rows=wait(lambda:self.elements(value,using),bool,timeout=20)
        require(len(rows)==1,'Ambiguous native target')
        key=rows[0].get('element-6066-11e4-a52e-4f735466cecf') or rows[0]['ELEMENT']
        self.call('/element/'+key+'/click','POST',{})

    def source(self):return ET.fromstring(self.call('/source'))

    def restart_app(self):
        for command in ('mobile: terminateApp','mobile: activateApp'):
            self.call('/execute/sync','POST',{'script':command,'args':[{'bundleId':self.bundle_id}]})
        wait(lambda:self.elements(self.text_predicate('我的')),bool,timeout=30)

    def snapshot(self,output,name):
        source=self.call('/source')
        (Path(output)/(name+'.xml')).write_text(source)
        filename = self.screenshot(output, name)
        run = getattr(self, '_evidence_run', None)
        if run and run.report['cases'] and run.report['cases'][-1]['status'] == 'running':
            run.report['cases'][-1].setdefault('screenshots', []).append(
                {'path': filename, 'name': '检查现场：' + name})
        return ET.fromstring(source)

    def screenshot(self, output, name):
        data = base64.b64decode(self.call('/screenshot'), validate=True)
        require(data.startswith(b'\x89PNG\r\n\x1a\n'), 'Native screenshot is not PNG')
        filename = name + '.png'
        (Path(output) / filename).write_bytes(data)
        return filename

    def bind_evidence(self, run):
        self._evidence_run = run
        def capture(name, verification):
            filename = self.screenshot(run.output, 'case-' + name)
            return [{'path': filename, 'name': '用例结束现场' if verification != 'API'
                     else '接口检查结束时的设备画面（辅助，不替代接口断言）'}]
        run.capture_evidence = capture

    def back_to_list(self):
        # Verified build-64 header hierarchy: first child contains the back chevron.
        path='//*[@name="chat-conversation-subpage-header"]/XCUIElementTypeOther[1]/XCUIElementTypeOther[1]/XCUIElementTypeOther[1]'
        self.click(path,'xpath')
        wait(lambda:self.elements(self.text_predicate('私信')),bool,timeout=20)

    def assert_role(self,actor):
        """Start on main message list, then verify account in the Me page."""
        self.click(self.text_predicate('我的'))
        wait(lambda:self.elements(self.text_predicate(actor.name)),bool,timeout=20)
        self.click(self.text_predicate('消息'))

    def open_private(self,peer):
        self.click(self.text_predicate(peer.name))
        wait(lambda:self.elements('chat-conversation-subpage-header','accessibility id'),bool,timeout=20)

    def assert_latest(self,root,text):
        nodes=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText' and e.get('name')==text and e.get('visible')=='true']
        require(len(nodes)==1,'Latest message absent or ambiguous in viewport')
        composers=[e for e in root.iter() if e.get('name')=='输入消息...' and e.get('visible')=='true' and e.get('type')=='XCUIElementTypeStaticText']
        require(len(composers)==1,'Composer geometry unavailable')
        node=nodes[0];bottom=float(node.get('y'))+float(node.get('height'))
        require(float(node.get('y'))>=0 and bottom<=float(composers[0].get('y')),'Latest message obscured by composer or below viewport')

    def wait_latest(self,text):
        def visible(root):
            try:self.assert_latest(root,text);return True
            except AssertionError:return False
        return wait(self.source,visible,timeout=20)

    def stable_anchor_y(self,text):
        state={'y':None,'samples':0}
        def stable(root):
            nodes=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText'
                   and e.get('name')==text and e.get('visible')=='true']
            if len(nodes)!=1:
                state['samples']=0;return False
            y=float(nodes[0].get('y'))
            state['samples']=state['samples']+1 if state['y'] is not None and abs(y-state['y'])<1 else 1
            state['y']=y
            return state['samples']>=3
        wait(self.source,stable,timeout=10,interval=.5)
        return state['y']

    @staticmethod
    def receipt(root,text):
        parents={child:parent for parent in root.iter() for child in parent}
        targets=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText' and e.get('name')==text]
        if len(targets)!=1:return None
        node=targets[0]
        while node in parents:
            node=parents[node]
            texts=[e.get('name') for e in node.iter() if e.get('type')=='XCUIElementTypeStaticText']
            receipts=[x for x in texts if x in ('已发送','未读','已读','发送中','发送失败')]
            if receipts:return receipts[0] if len(receipts)==1 else None
        return None

    def private_observer(self,run):
        def observe(sent,read):
            if not read:self.open_private(run.actors['a'])
            text=sent[-1]['content']
            self.wait_latest(text)
            root=self.snapshot(run.output,'after-read' if read else 'before-read')
            self.assert_latest(root,text)
            if not read:
                require(all(self.receipt(root,x['content']) in ('已发送','未读') for x in sent),'Outgoing unread/send state missing')
                self.back_to_list();self.open_private(run.actors['a'])
                self.assert_latest(self.snapshot(run.output,'reentered-latest'),text)
            else:
                # Reentry also covers implementations that only refresh receipts on history fetch.
                self.back_to_list();self.open_private(run.actors['a'])
                try:
                    wait(lambda:self.source(),lambda r:all(self.receipt(r,x['content'])=='已读' for x in sent),timeout=20)
                finally:self.snapshot(run.output,'read-reentered')
        return observe


    def drag_history(self,direction):
        root=self.source()
        headers=[e for e in root.iter() if e.get('name')=='chat-conversation-subpage-header']
        composers=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText' and e.get('name')=='输入消息...' and e.get('visible')=='true']
        require(len(headers)==1 and len(composers)==1,'Conversation viewport unavailable')
        top=float(headers[0].get('y'))+float(headers[0].get('height'))+20
        bottom=float(composers[0].get('y'))-30
        x=float(headers[0].get('x'))+float(headers[0].get('width'))/2
        require(bottom-top>150,'History viewport too small')
        first,last=(top+(bottom-top)*.2,top+(bottom-top)*.8)
        if direction=='newer':first,last=last,first
        self.call('/execute/sync','POST',{'script':'mobile: dragFromToForDuration','args':[{
            'duration':.6,'fromX':x,'fromY':first,'toX':x,'toY':last}]})

    def history_incoming(self,run):
        from .business import ROOT
        from .core import segment
        sender,recipient=run.actors['a'],run.actors['c']
        sent=[]
        with run.case('private.history-recipient-baseline'):
            require(run.messages.unread(recipient,sender)==0,'Existing unread messages must be preserved')
        def send(label):
            message=run.messages.send(sender,recipient.user_id,'历史定位'+run.run_id[:8]+'-'+label)
            sent.append(message)
            run.report['resources'].append({'kind':'private-message','id':str(message['messageId']),
                'status':'retained','reason':'Existing conversation is not cleared'})
            run.save()
            return message
        try:
            with run.case('private.history-scroll-anchor-preparation') as row:
                row['verification']='native-UI'
                self.open_private(sender)
                history=run.messages.history(recipient,sender.user_id,direction='older')
                contents=[x.get('content') for x in history.values() if x.get('contentType')=='TEXT' and x.get('content')]
                unique={x for x in contents if contents.count(x)==1}
                self.drag_history('older')
                root=self.snapshot(run.output,'older-history-before-incoming')
                header=next(e for e in root.iter() if e.get('name')=='chat-conversation-subpage-header')
                composer=next(e for e in root.iter() if e.get('name')=='输入消息...' and e.get('type')=='XCUIElementTypeStaticText')
                candidates=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText' and e.get('visible')=='true'
                    and e.get('name') in unique and float(e.get('y'))>float(header.get('y'))+float(header.get('height'))
                    and float(e.get('y'))+float(e.get('height'))<float(composer.get('y'))]
                require(bool(candidates),'No unique old-history text anchor visible')
                anchor=candidates[0].get('name');anchor_y=self.stable_anchor_y(anchor)
                self.snapshot(run.output,'older-history-stable-before-incoming')
                run.report['history_anchor']={'message_id':next(k for k,x in history.items() if x.get('content')==anchor),'y_before':anchor_y}
            with run.case('private.incoming-does-not-pull-old-history') as row:
                row['verification']='native-UI-and-API'
                incoming=send('old-view')
                # Verify actual recipient persistence before observing viewport behavior.
                run.messages.history(recipient,sender.user_id,expected_ids=[str(incoming['messageId'])],direction='older')
                # History GET does not mark read. Require the native client to
                # have processed this incoming message before checking the anchor.
                wait(lambda:(self.source(),run.messages.unread(recipient,sender)),
                    lambda value:value[1]==0 or any(e.get('name')==incoming['content'] for e in value[0].iter()),timeout=20)
                root=self.snapshot(run.output,'older-history-after-incoming')
                anchors=[e for e in root.iter() if e.get('type')=='XCUIElementTypeStaticText' and e.get('name')==anchor and e.get('visible')=='true']
                require(len(anchors)==1,'Incoming message forced old-history anchor out of viewport')
                after=float(anchors[0].get('y'));run.report['history_anchor']['y_after']=after
                require(abs(after-anchor_y)<=3,'Incoming message changed old-history scroll position')
            with run.case('private.bottom-follows-newest-incoming') as row:
                row['verification']='native-UI-and-API'
                for _ in range(5):
                    self.drag_history('newer')
                    root=self.source()
                    try:self.assert_latest(root,incoming['content']);break
                    except AssertionError:continue
                else:raise AssertionError('Could not return to newest message')
                latest=send('bottom-view')
                self.wait_latest(latest['content'])
                self.assert_latest(self.snapshot(run.output,'bottom-newest-incoming'),latest['content'])
            run.report['native_ui']='history-anchor-and-bottom-follow-verified'
        finally:
            # Baseline was zero; mark only this run's incoming messages as read.
            if sent:
                try:
                    count=run.messages.unread(recipient,sender)
                    require(count<=len(sent),'Unrelated unread arrived; preserve it')
                    run.api.request(recipient,'POST',ROOT+'/private-conversations/'+segment(sender.user_id)+'/read')
                    require(run.messages.unread(recipient,sender)==0,'Incoming unread cleanup not confirmed')
                except Exception as exc:run.report['unread_cleanup_error']=type(exc).__name__
            run.save()


    def bottom_incoming(self, run):
        from .business import ROOT
        from .core import segment
        ui = self
        sender,recipient=run.actors['a'],run.actors['c']
        sent=[];baseline_ok=False
        try:
            with run.case('private.independent-bottom-baseline') as row:
                row['verification'] = 'native-UI-and-API'
                require(run.messages.unread(recipient,sender)==0,'Preserve existing unread before bottom-follow test')
                baseline_ok=True
                if ui.elements('chat-conversation-subpage-header','accessibility id'):ui.back_to_list()
                if not ui.elements(ui.text_predicate('我的')):ui.restart_app()
                ui.assert_role(recipient)
                ui.open_private(sender)
                history=run.messages.history(recipient,sender.user_id,direction='older')
                latest=max(history.values(),key=lambda x:(x.get('createdAtEpochMillis',0),str(x['messageId'])))
                require(latest.get('contentType')=='TEXT' and latest.get('content'),'Text baseline required for current conversation')
                ui.wait_latest(latest['content'])
                ui.snapshot(run.output,'bottom-baseline')
            for index in range(3):
                with run.case('private.bottom-follows-incoming-'+str(index+1)) as row:
                    row['verification']='native-UI-and-API'
                    message=run.messages.send(sender,recipient.user_id,'底部跟随'+run.run_id[:8]+'-'+str(index))
                    sent.append(message)
                    run.report['resources'].append({'kind':'private-message','id':str(message['messageId']),
                        'status':'retained','reason':'Existing conversation not cleared'})
                    run.save()
                    ui.wait_latest(message['content'])
                    ui.snapshot(run.output,'bottom-after-incoming-'+str(index+1))
            with run.case('private.bottom-delivery-and-unread'):
                history=run.messages.history(recipient,sender.user_id,expected_ids=[str(x['messageId']) for x in sent],direction='older')
                for message in sent:
                    incoming=history[str(message['messageId'])]
                    require(incoming.get('direction')=='INBOUND' and incoming.get('content')==message['content'],'Recipient message mismatch')
                wait(lambda:run.messages.unread(recipient,sender),lambda value:value==0)
            run.report['native_ui']='three-incoming-messages-followed-at-bottom'
        except Exception:
            pass
        finally:
            if baseline_ok and sent:
                try:
                    count=run.messages.unread(recipient,sender)
                    require(count<=len(sent),'Unrelated unread arrived; preserve it')
                    if count:
                        run.api.request(recipient,'POST',ROOT+'/private-conversations/'+segment(sender.user_id)+'/read')
                    require(run.messages.unread(recipient,sender)==0,'Unread cleanup unconfirmed')
                except Exception as exc:run.report['unread_cleanup_error']=type(exc).__name__
            run.save()

    def assert_mixed_display(self, run, sent):
        from .private_mixed import mixed_display_regions, assert_fixture_pixels
        from .media import fixture_png
        root = self.snapshot(run.output, 'mixed-' + run.report['cases'][-1]['name'])
        texts, regions = mixed_display_regions(root, sent)
        self.assert_latest(root, sent[-1]['content'])
        width = float(next(e for e in root.iter() if e.get('type') == 'XCUIElementTypeApplication').get('width'))
        proofs = []
        for label, region in zip(('image-1', 'image-2'), regions):
            png = fixture_png(run.run_id + run.actors['a'].user_id + label)
            path = run.output / ('mixed-' + run.report['cases'][-1]['name'] + '.png')
            proofs.append({'image': label, 'region': region,
                           'matched_ratio': assert_fixture_pixels(path, png, region, width)})
        run.report['cases'][-1]['image_display_checks'] = proofs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accounts',required=True)
    parser.add_argument('--session',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--suite',choices=('private','history','bottom','mixed'),default='private')
    args=parser.parse_args()
    run=LiveRun(args.accounts,args.output)
    ui=OwnedIOS(args.session)
    if ui.elements('chat-conversation-subpage-header','accessibility id'):ui.back_to_list()
    if not ui.elements(ui.text_predicate('我的')):ui.restart_app()
    ui.assert_role(run.actors['c'])
    ui.bind_evidence(run)
    try:
        if args.suite=='history':ui.history_incoming(run)
        elif args.suite=='bottom':ui.bottom_incoming(run)
        elif args.suite=='mixed':
            from .private_mixed import run_mixed
            run_mixed(run, ui)
        else:run.private_text(ui.private_observer(run))
    except Exception:pass
    run.save()
    return 1 if any(x['status']!='passed' for x in run.report['cases']) or run.report.get('unread_cleanup_error') else 0


if __name__=='__main__':raise SystemExit(main())
