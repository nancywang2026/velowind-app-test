from collections import OrderedDict
from io import BytesIO
from xml.etree import ElementTree as E
import pytest
from PIL import Image
from velowind_appium.message_regression.private_mixed import assert_history_sequence, mixed_display_regions, assert_fixture_pixels
from velowind_appium.message_regression.media import fixture_png


def messages():
    return [{'messageId': str(i), 'contentType': 'TEXT' if i%2==0 else 'IMAGE', 'content': str(i), 'direction': 'INBOUND'} for i in range(5)]


def test_history_order_checks_actual_order_and_direction():
    rows = messages()
    assert assert_history_sequence(OrderedDict((x['messageId'],x) for x in rows),rows,'INBOUND') == rows
    with pytest.raises(AssertionError, match='order'):
        assert_history_sequence(OrderedDict((x['messageId'],x) for x in reversed(rows)),rows,'INBOUND')
    with pytest.raises(AssertionError, match='direction'):
        assert_history_sequence(OrderedDict((x['messageId'],x) for x in rows),rows,'OUTBOUND')


def test_display_regions_exclude_avatar_and_reject_missing_image():
    root = E.fromstring('<root>' + ''.join(f'<e type="XCUIElementTypeStaticText" name="{i}" y="{20+i*100}" height="20" visible="true"/>' for i in (0,2,4)) +
                        '<e name="image" x="20" y="70" width="90" height="90" visible="true"/>' +
                        '<e name="image" x="20" y="270" width="90" height="90" visible="true"/>' +
                        '<e name="image" x="0" y="60" width="32" height="32" visible="true"/></root>')
    _, boxes = mixed_display_regions(root,messages())
    assert len(boxes)==2
    root.remove(root[3])
    with pytest.raises(AssertionError,match='image bubble'):
        mixed_display_regions(root,messages())


def test_pixels_accept_fixture_and_reject_blank_or_different_image(tmp_path):
    png=fixture_png('fixture1')
    path=tmp_path/'screen.png';path.write_bytes(png)
    assert assert_fixture_pixels(path,png,(0,0,64,64),64)==1
    Image.new('RGB',(64,64),'white').save(path)
    with pytest.raises(AssertionError,match='pixels'):
        assert_fixture_pixels(path,png,(0,0,64,64),64)
    path.write_bytes(fixture_png('fixture2'))
    with pytest.raises(AssertionError,match='pixels'):
        assert_fixture_pixels(path,png,(0,0,64,64),64)


def test_private_image_result_query_requires_original_entry_and_no_resend():
    from unittest.mock import Mock
    from velowind_appium.message_regression.business import Messages
    from velowind_appium.message_regression.core import Actor
    actor=Actor('a','A','not-real')
    api=Mock()
    message={'messageId':'persisted','senderUserId':'a','content':None,'clientMessageId':'original-request'}
    api.request.side_effect=[{'messageId':'provisional'}, {'status':'SENT','contentAvailable':True,'message':message}]
    assert Messages(api).send(actor,'c','',image_ids=['asset'],client_id='original-request')==message
    assert api.request.call_args.kwargs['params']=={'sendEntry':'CONVERSATION'}
    assert api.request.call_args.args[2].endswith('/original-request')
    assert sum(call.args[1]=='POST' for call in api.request.call_args_list)==1
