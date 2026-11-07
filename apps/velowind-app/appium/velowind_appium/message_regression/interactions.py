"""Append comment notification checks on a caller-supplied existing C-owned post.

This flow never republishes a note. The same post and current-run comments are
reused for mention, reply, like and favorite; only those comments are deleted.
"""
import argparse
from .core import Blocked, identifier, require, segment, wait
from .live import LiveRun


def comment_notifications(run,post_id,verify_ui=None):
    a,b,c=(run.actors[r] for r in 'abc')
    target='/api/v1/mobile/ugc/comment-targets/POST/'+segment(post_id)+'/comments'
    resources=[];reactions=[]
    def rows():return run.api.pages(a,target,id_key='commentId',params={'sort':'LATEST'})
    def create_comment(actor,text,**kwargs):
        item={'kind':'comment','id':None,'status':'creation-pending','post_id':post_id}
        resources.append((actor,item));run.report['resources'].append(item);run.save()
        def registered(result):
            item.update(id=identifier(result['commentId']),status='created');run.save()
        try:
            return run.messages.comment(actor,'POST',post_id,text,on_created=registered,**kwargs)
        finally:
            if item['id'] is None:
                try:
                    roots=rows()
                    candidates=roots+[reply for row in roots for reply in row.get('replyPreview',[])]
                    matches=[x for x in candidates if x.get('content')==text and str(x.get('userId'))==actor.user_id]
                    if len(matches)==1:item.update(id=str(matches[0]['commentId']),status='reconciled')
                    else:item['status']='cleanup-pending'
                except Exception:item['status']='cleanup-pending'
                run.save()
    def notify(recipient,baseline,biz_id,kind):
        detail=run.messages.notification_after(recipient,baseline,biz_id,kind,category='INTERACTION')
        require(detail.get('notificationType')==kind,'Notification type mismatch')
        if verify_ui:verify_ui(recipient,detail)
        return detail
    with run.case('comments.existing-owned-post-preparation'):
        detail=run.api.request(c,'GET','/api/v1/mobile/posts/'+segment(post_id))
        require(str(detail.get('postId'))==post_id and str(detail.get('authorUserId'))==c.user_id,'Existing post must belong to test C')
        require(detail.get('commentsEnabled') is True,'Selected post does not accept comments')
        baseline={r:{str(x['inboxId']) for x in run.messages.notifications(run.actors[r],category='INTERACTION')} for r in 'abc'}
    try:
        with run.case('comments.publish-real-mention-and-notification'):
            root=create_comment(a,'消息自动化@'+c.name+' '+run.run_id[:8],mentions=[c.user_id])
            require(any(str(x.get('mentionedUserId'))==c.user_id for x in root.get('mentions',[])),'Published structured mention is missing')
            notify(c,baseline['c'],root['commentId'],'CONTENT_COMMENT_MENTIONED')
        with run.case('comments.reply-and-notification'):
            reply=create_comment(b,'消息自动化回复 '+run.run_id[:8],reply_to=root['commentId'])
            require(str(reply.get('rootCommentId'))==str(root['commentId']),'Reply root mismatch')
            notify(a,baseline['a'],reply['commentId'],'CONTENT_COMMENT_REPLIED')
        for action,kind in [('LIKE','CONTENT_COMMENT_LIKED'),('FAVORITE','CONTENT_COMMENT_FAVORITED')]:
            with run.case('comments.'+action.lower()+'-and-notification'):
                body={'targetType':'COMMENT','targetId':root['commentId'],'actionType':action}
                reactions.append(body)  # Compensation registered before mutation.
                result=run.api.request(b,'POST','/api/v1/mobile/ugc/interactions',body=body)
                require(result.get('active') is True,'Comment reaction did not become active')
                flag='likedByCurrentUser' if action=='LIKE' else 'favoritedByCurrentUser'
                def current():
                    row=next(x for x in run.api.pages(b,target,id_key='commentId') if str(x['commentId'])==str(root['commentId']))
                    run.report.setdefault('reaction_observations',{})[action]={
                        'flag_present':flag in row,'value':row.get(flag),
                        'count':row.get('likeCount' if action=='LIKE' else 'favoriteCount')}
                    return row
                # Current deployment omits per-user flags from this public read.
                # This run owns the new comment (zero reactions); authenticate
                # the mutation and verify its persisted counter before notification.
                count='likeCount' if action=='LIKE' else 'favoriteCount'
                wait(current,lambda row:row.get(count)==1)
                notify(a,baseline['a'],root['commentId'],kind)
    finally:
        cleanup_errors=[]
        for body in reversed(reactions):
            try:
                result=run.api.request(b,'DELETE','/api/v1/mobile/ugc/interactions',body=body)
                run.report.setdefault('reaction_cleanup_ack',{})[body['actionType']]=result.get('active')
                def cleared():
                    current=next((x for x in rows() if str(x['commentId'])==str(body['targetId'])),None)
                    return current is None or current.get('likeCount' if body['actionType']=='LIKE' else 'favoriteCount')==0
                wait(cleared,bool)
            except Exception as exc:cleanup_errors.append(type(exc).__name__)
        for actor,item in reversed(resources):
            try:
                require(bool(item['id']),'Unknown comment outcome requires reconciliation')
                run.api.request(actor,'DELETE','/api/v1/mobile/ugc/comments/'+segment(item['id']))
                item['status']='deleted-pending-verification'
            except Exception as exc:item.update(status='cleanup-pending',error=type(exc).__name__)
        try:
            remaining={str(x['commentId']) for x in rows()}
            for _,item in resources:
                if item['id'] in remaining or item['status']=='cleanup-pending':item['status']='cleanup-pending'
                else:item['status']='deleted'
        except Exception as exc:
            for _,item in resources:item.update(status='cleanup-pending',error=type(exc).__name__)
        if cleanup_errors:run.report['reaction_cleanup_errors']=cleanup_errors
        run.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accounts',required=True)
    parser.add_argument('--post-id',required=True,help='Existing published C-owned note; reuse current business test ID')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    run=LiveRun(args.accounts,args.output)
    try:comment_notifications(run,args.post_id)
    except Exception:pass
    run.save()
    failed=any(x['status']!='passed' for x in run.report['cases'])
    pending=any(x['status']=='cleanup-pending' for x in run.report['resources']) or bool(run.report.get('reaction_cleanup_errors'))
    print({'passed':sum(x['status']=='passed' for x in run.report['cases']),'failed':failed,'cleanup_pending':bool(pending)})
    return int(failed or pending)


if __name__=='__main__':raise SystemExit(main())
