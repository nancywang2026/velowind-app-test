"""Upload a reproducible PNG using dev-issued OSS policy; never log signed URLs."""
import hashlib
import struct
import uuid
import zlib
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.error import HTTPError, URLError
from .core import ApiFailure, require


def fixture_png(seed):
    digest=hashlib.sha256(seed.encode()).digest()
    width=height=64
    rows=b''.join(b'\0'+b''.join(bytes(digest[(x//8+y//8)%2*3:(x//8+y//8)%2*3+3]) for x in range(width)) for y in range(height))
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def trusted_url(url):
    parsed=urlsplit(url)
    require(parsed.scheme=='https' and not parsed.username and not parsed.password and
            parsed.hostname and (parsed.hostname.endswith('.aliyuncs.com') or parsed.hostname.endswith('.velowind.com')),
            'Unexpected signed media host')
    return url


def multipart(fields,png,boundary):
    parts=[]
    for key,value in fields.items():
        require('\r' not in str(value) and '\n' not in str(value),'Invalid upload field')
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="message-test.png"\r\nContent-Type: image/png\r\n\r\n'.encode(),png,f'\r\n--{boundary}--\r\n'.encode()])
    return b''.join(parts)


def upload_group_image(run,actor,group_id):
    return upload_message_image(run, actor, group_id, group=True)


def upload_private_image(run, actor, peer_id, *, label):
    return upload_message_image(run, actor, peer_id, group=False, label=label)


def upload_message_image(run, actor, target_id, *, group, label=''):
    png=fixture_png(run.run_id+actor.user_id+label)
    config=run.api.request(actor,'POST','/api/v1/mobile/oss/client-upload-config',body={
        'targetType':'CHATROOM_MESSAGE_IMAGE' if group else 'PRIVATE_MESSAGE_IMAGE',
        'targetId':target_id,'contentType':'image/png',
        'fileName':'message-test.png','size':len(png)})
    asset_id=config['assetId']
    resource={'kind':'media-asset','id':asset_id,'status':'upload-pending',
              'sha256':hashlib.sha256(png).hexdigest(),'residual':
              'No asset deletion API used; retained in test conversation'}
    run.report['resources'].append(resource);run.save()
    fields={'key':config['objectKey'],'OSSAccessKeyId':config['accessKeyId'],'policy':config['policy'],
            'Signature':config['signature'],'success_action_status':'200','Content-Type':'image/png'}
    if config.get('securityToken'):fields['x-oss-security-token']=config['securityToken']
    if config.get('forbidOverwrite'):fields['x-oss-forbid-overwrite']='true'
    if config.get('objectAcl'):fields['x-oss-object-acl']=config['objectAcl']
    boundary='message-'+uuid.uuid4().hex
    request=Request(trusted_url(config['host']),data=multipart(fields,png,boundary),method='POST',
                    headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with run.api.opener.open(request,timeout=30) as response:
            etag=response.headers.get('ETag');response.read(4096)
        require(bool(etag),'OSS did not return actual ETag')
    except (HTTPError,URLError,OSError,TimeoutError) as exc:
        if isinstance(exc,HTTPError):exc.close()
        resource['status']='upload-unknown';run.save()
        raise ApiFailure() from None
    run.api.request(actor,'POST','/api/v1/mobile/oss/upload-callback',body={
        'key':config['objectKey'],'bucket':config['bucket'],'assetId':asset_id,
        'etag':etag,'size':len(png),'mimeType':'image/png'})
    resource['status']='uploaded-retained';run.save()
    return asset_id,png


def assert_media_bytes(run,message,asset_id,expected):
    items=message.get('mediaItems') or []
    require(len(items)==1 and str(items[0]['assetId'])==str(asset_id),'Wrong image asset delivered')
    item=items[0]
    require(item['displayStatus']=='AVAILABLE','Uploaded image is not available')
    try:
        with run.api.opener.open(Request(trusted_url(item['accessUrl'])),timeout=20) as response:
            actual=response.read(5_242_881)
    except (HTTPError,URLError,OSError,TimeoutError) as exc:
        if isinstance(exc,HTTPError):exc.close()
        raise ApiFailure() from None
    require(hashlib.sha256(actual).digest()==hashlib.sha256(expected).digest(),'Full image bytes do not match current fixture')
