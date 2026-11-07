"""Private text/image ordering checks. API sending and native display are separate."""
import time
from .business import ROOT
from .core import require, segment, wait
from .media import upload_private_image, assert_media_bytes


def assert_history_sequence(rows, expected, direction):
    ids = [str(x['messageId']) for x in expected]
    actual = [x for x in rows.values() if str(x['messageId']) in ids]
    require([str(x['messageId']) for x in actual] == ids, 'Mixed messages missing, duplicated or out of send order')
    for actual_message, sent in zip(actual, expected):
        require(actual_message.get('contentType') == sent['contentType'], 'Mixed message type mismatch')
        require(actual_message.get('direction') == direction, 'Mixed message direction mismatch')
        if sent['contentType'] == 'TEXT':
            require(actual_message.get('content') == sent['content'], 'Mixed text body mismatch')
    return actual


def run_mixed(run, ui):
    sender, recipient = run.actors['a'], run.actors['c']
    sent = []
    images = {}
    baseline_ok = False
    try:
        with run.case('private.mixed-data-preparation'):
            require(run.messages.unread(recipient, sender) == 0, 'Preserve pre-existing unread')
            baseline_ok = True
            for label in ('image-1', 'image-2'):
                asset, png = upload_private_image(run, sender, recipient.user_id, label=label)
                images[label] = (asset, png)
                (run.output / (label + '.png')).write_bytes(png)
        with run.case('private.mixed-text-image-send'):
            # Existing test-environment baseline: 3/pair/minute, 5/sender/minute.
            # Start a fresh window and pace new sends; never retry failed writes.
            time.sleep(61)
            for index, kind in enumerate(('TEXT', 'IMAGE', 'TEXT', 'IMAGE', 'TEXT')):
                if index:
                    time.sleep(21)
                if kind == 'TEXT':
                    message = run.messages.send(sender, recipient.user_id, '混合顺序'+run.run_id[:8]+'-'+str(index+1))
                else:
                    asset, png = images['image-1' if index == 1 else 'image-2']
                    message = run.messages.send(sender, recipient.user_id, '', image_ids=[asset])
                sent.append(message)
                run.report['resources'].append({'kind': 'private-message', 'id': str(message['messageId']),
                    'status': 'retained', 'reason': 'Existing conversation history preserved'})
                run.save()
            require(len({str(x['messageId']) for x in sent}) == 5, 'Duplicate send acknowledgement')
        with run.case('private.mixed-both-history-order-and-image-bytes'):
            ids = [str(x['messageId']) for x in sent]
            for actor, peer, direction in ((sender, recipient, 'OUTBOUND'), (recipient, sender, 'INBOUND')):
                history = run.messages.history(actor, peer.user_id, expected_ids=ids, direction='older')
                actual = assert_history_sequence(history, sent, direction)
                for index, label in ((1, 'image-1'), (3, 'image-2')):
                    asset, png = images[label]
                    assert_media_bytes(run, actual[index], asset, png)
            wait(lambda: run.messages.unread(recipient, sender), lambda count: count == 5)
        with run.case('private.mixed-native-display-order') as row:
            row['verification'] = 'native-UI-and-API'
            ui.open_private(sender)
            ui.wait_latest(sent[-1]['content'])
            ui.snapshot(run.output, 'mixed-latest')
            ui.assert_mixed_display(run, sent)
        with run.case('private.mixed-reentry-display-order') as row:
            row['verification'] = 'native-UI'
            ui.back_to_list()
            ui.open_private(sender)
            ui.wait_latest(sent[-1]['content'])
            ui.assert_mixed_display(run, sent)
    finally:
        if baseline_ok and sent:
            try:
                count = run.messages.unread(recipient, sender)
                require(count <= len(sent), 'Unrelated unread arrived; preserve it')
                if count:
                    run.api.request(recipient, 'POST', ROOT+'/private-conversations/'+segment(sender.user_id)+'/read')
                require(run.messages.unread(recipient, sender) == 0, 'Mixed-message unread cleanup unconfirmed')
            except Exception as exc:
                run.report['unread_cleanup_error'] = type(exc).__name__
        run.save()


def mixed_display_regions(root, sent):
    """Locate three unique text anchors and two image-sized regions between them.

    Current native build exposes generic image names; geometry excludes avatars.
    PNG pixel checks below must still prove that the regions contain our fixtures.
    """
    texts = []
    for index in (0, 2, 4):
        nodes = [e for e in root.iter() if e.get('type') == 'XCUIElementTypeStaticText'
                 and e.get('name') == sent[index]['content'] and e.get('visible') == 'true']
        require(len(nodes) == 1, 'Mixed text is missing, duplicated or not visible')
        texts.append(nodes[0])
    ys = [float(e.get('y')) for e in texts]
    require(ys[0] < ys[1] < ys[2], 'Mixed text display order is incorrect')
    regions = []
    for low, high in zip(texts, texts[1:]):
        top = float(low.get('y')) + float(low.get('height'))
        bottom = float(high.get('y'))
        boxes = set()
        for e in root.iter():
            if e.get('visible') != 'true' or e.get('name') != 'image':
                continue
            x, y, width, height = [float(e.get(k, 0)) for k in ('x', 'y', 'width', 'height')]
            if width >= 60 and height >= 60 and y >= top and y + height <= bottom:
                boxes.add((x, y, width, height))
        require(len(boxes) == 1, 'Expected one unambiguous image bubble between text anchors')
        regions.append(next(iter(boxes)))
    return texts, regions


def assert_fixture_pixels(screenshot, fixture, region, logical_width):
    from io import BytesIO
    from PIL import Image, ImageOps
    actual = Image.open(screenshot).convert('RGB')
    scale = actual.width / logical_width
    x, y, width, height = region
    crop = actual.crop((round(x*scale), round(y*scale), round((x+width)*scale), round((y+height)*scale)))
    expected = ImageOps.fit(Image.open(BytesIO(fixture)).convert('RGB'), crop.size)
    matching = 0
    # Sample tile centers, avoiding interpolation boundaries and rounded corners.
    for row in range(1, 7):
        for column in range(1, 7):
            point = (round((column+.5)*crop.width/8), round((row+.5)*crop.height/8))
            a, b = crop.getpixel(point), expected.getpixel(point)
            matching += max(abs(v-w) for v, w in zip(a, b)) <= 30
    require(matching >= 33, 'Rendered image pixels do not match the current fixture (blank, placeholder or wrong image)')
    return matching / 36
