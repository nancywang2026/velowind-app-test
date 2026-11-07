"""Reuse the existing physical-device note publication case, then verify notice.

Requires an explicitly owned session already logged into C. Admin A only acts on
new IDs captured by PostPublicationObserver; existing notes are never moderated.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from appium import webdriver
from appium.options.common import AppiumOptions

from .core import require, wait
from .ios_live import OwnedIOS
from .live import LiveRun
from .publication import PostPublicationObserver


def run_note(accounts_file,session_file,output,*,use_case='publish-note-changbaishan',outcome='approve'):
    from tests.shared_publish_note import run_publish_note_case
    from velowind_appium.config import load_ios_config
    run=LiveRun(accounts_file,output)
    source=json.loads(Path(accounts_file).read_text())['accounts']
    admin=run.api.login_admin(source['a']['username'],source['a']['password'],
                             expected_id=source['a']['user_id'],name=source['a']['name'])
    ui=OwnedIOS(session_file)
    if ui.elements('chat-conversation-subpage-header','accessibility id'):ui.back_to_list()
    if not ui.elements(ui.text_predicate('我的')):ui.restart_app()
    ui.assert_role(run.actors['c'])
    data=json.loads(Path(session_file).read_text())
    class AttachedDriver(webdriver.Remote):
        def start_session(self,capabilities):
            self.session_id=data['session_id']
            self.caps={'platformName':'iOS','appium:automationName':'XCUITest'}
    driver=AttachedDriver(command_executor=data['server'],options=AppiumOptions())
    driver.implicitly_wait(0)
    config=replace(load_ios_config(),login_username=source['c']['username'],login_password=source['c']['password'])
    def verify_ui(detail):
        # Main tab text is unique outside the message screen.
        ui.click(ui.text_predicate('消息'))
        ui.click(ui.text_predicate('系统通知'))
        content=detail.get('content')
        require(isinstance(content,str) and bool(content),'Notification content missing')
        wait(lambda:ui.elements(ui.text_predicate(content)),bool,timeout=20)
        ui.snapshot(run.output,'published-note-notification-list')
        run.report['native_ui']='current-note-system-notification-visible'
        ui.click('message-system-back-button','accessibility id')
    observer=PostPublicationObserver(run.api,run.actors['c'],admin,verify_ui,outcome=outcome)
    def step(name,action,**kwargs):
        with run.case('note.'+name) as row:
            row['verification']='native-UI-and-business-API'
            return action()
    try:
        run_publish_note_case(driver,config,step,use_case,verification_label='message-publication',
                              assertion_label='iOS',notification_observer=observer)
    except Exception as exc:
        # The step report carries sanitized failure evidence; never print driver errors.
        run.report['publication_error']=type(exc).__name__
        publication=getattr(driver,'_api_note_publication',None)
        if publication:
            run.report['publication_scope']={key:publication.get(key)
                for key in ('requested_title','published_title','post_id')}
    finally:
        if observer.existing_ids is not None:
            # Reconcile even if the UI publication raised before returning its toast.
            from tests.shared_publish_note import load_message_note_draft,TESTDATA_PATH
            title=load_message_note_draft(use_case,testdata_path=TESTDATA_PATH).title
            publication=getattr(driver,'_api_note_publication',None)
            if publication and publication.get('requested_title')==title:
                title=publication['published_title']
            try:
                current=[x for x in observer.mine() if str(x['postId']) not in observer.existing_ids and x.get('title')==title]
                for note in current:
                    resource={'kind':'post','id':str(note['postId']),'status':'cleanup-pending'}
                    run.report['resources'].append(resource)
                    if note.get('publishStatus')!='DELETED':
                        run.api.request(run.actors['c'],'DELETE','/api/v1/mobile/posts/'+resource['id'])
                    def gone():
                        return all(str(x['postId'])!=resource['id'] or x.get('publishStatus')=='DELETED' for x in observer.mine())
                    wait(gone,bool);resource['status']='deleted'
            except Exception as exc:
                run.report['publication_cleanup_error']=type(exc).__name__
        run.save()
    failed=any(x['status']!='passed' for x in run.report['cases']) or bool(run.report.get('publication_error'))
    return int(failed or bool(run.report.get('publication_cleanup_error')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accounts',required=True)
    parser.add_argument('--session',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--outcome',choices=('approve','reject'),default='approve')
    parser.add_argument('--use-case',default='publish-note-changbaishan')
    args=parser.parse_args()
    return run_note(args.accounts,args.session,args.output,use_case=args.use_case,outcome=args.outcome)


if __name__=='__main__':raise SystemExit(main())
