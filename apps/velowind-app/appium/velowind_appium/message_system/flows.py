"""Eight business flows. Business fixtures and expected values live in YAML."""
from .config import resolve


class MessageFlows:
    def __init__(self, ui, bridge, data, case_id, runtime, context, variant):
        self.ui, self.bridge = ui, bridge
        self.case_id, self.variant = case_id, variant
        self.runtime = runtime
        self.case = resolve(data.case(case_id), {**context, 'runtime': runtime})
        self.input = self.case.get('input', {})
        self.expected = self.case['expected']

    def entity(self, alias):
        value = self.runtime[alias]['id']
        assert isinstance(value, str) and value, f'Missing entity ID: {alias}'
        return value

    def state(self, kind, alias, **expected):
        return self.bridge.wait(
            lambda: self.bridge.read(kind, self.entity(alias)),
            lambda value: all(value.get(k) == v for k, v in expected.items()),
            f'{kind} {alias}: {list(expected)}',
        )

    def synced(self, message_id, user_id):
        self.bridge.wait(lambda: self.bridge.read('delivery', message_id),
                         lambda v: user_id in v['synchronized_user_ids'], 'recipient synchronized message')

    def unread(self, count):
        e = self.expected
        self.ui.expect_text('home.system_unread', count)
        self.ui.expect_text('home.interaction_unread', e['unchanged_interaction_unread'])
        self.bridge.wait(lambda: self.bridge.read('unread', self.entity('actor')),
                         lambda v: v['system'] == count and v['interaction'] == e['unchanged_interaction_unread'],
                         'independent unread counters')

    def notification(self):
        u, e = self.ui, self.expected
        self.unread(e['initial_system_unread'])
        u.click('home.system')
        u.element('notification_list.ready')
        for alias in ('N1', 'N2', 'N3'):
            self.state('notification', alias, read=e['other_system_notifications_read'])
        u.back('home.ready')
        self.unread(e['after_list_open_system_unread'])
        for _ in range(self.input['repeat_open_count']):
            u.click('home.system')
            u.click('notification.row', id=self.input['target_notification'])
            u.element('target.ready')
            self.state('notification', 'N1', read=e['target_read'])
            u.back('notification_list.ready')
            u.back('home.ready')
            self.unread(e['after_target_open_system_unread'])
        self.unread(e['after_repeat_open_system_unread'])
        for alias in ('N2', 'N3'):
            self.state('notification', alias, read=e['other_system_notifications_read'])
        # The independently seeded interaction events must remain unread.
        for alias in ('I1', 'I2'):
            self.state('notification', alias, read=e['other_system_notifications_read'])

    def hidden(self):
        u, e, b = self.ui, self.expected, self.bridge
        cid = self.input['conversation_id']
        assert cid in u.collection('home_conversations')
        u.home()  # Reset list to top after complete traversal.
        u.hold_conversation(cid)
        u.click('conversation.hide')
        self.state('conversation', 'C', hidden=e['hidden_after_action'])
        sent = b.call('send', sender_id=self.entity('peer'), conversation_id=cid, text=self.input['incoming_text'])
        self.synced(sent['id'], self.entity('actor'))
        self.state('conversation', 'C', hidden=e['hidden_after_incoming_sync'])
        u.home()
        assert (cid in u.collection('home_conversations')) == e['in_home_after_incoming_sync']
        u.home()
        u.click('home.hidden')
        assert (cid in u.collection('hidden_conversations')) == e['in_hidden_list_after_incoming_sync']
        u.back('home.ready')
        u.click('home.hidden')
        u.open_conversation(cid)
        u.wait(lambda: u.visible_message_count(sent['id']) == e['incoming_message_count'], 'hidden chat incoming bubble')
        u.expect_text('chat.message', self.input['incoming_text'], id=sent['id'])
        state = b.read('conversation', cid)
        assert state['message_ids'].count(sent['id']) == e['incoming_message_count']
        assert (self.entity('M0') in state['message_ids']) == e['original_message_preserved']

    def messaging(self):
        u, b, e = self.ui, self.bridge, self.expected
        cid = self.entity('C')
        u.open_conversation(cid)
        u.send(self.input['outbound_text'])
        result = b.wait(lambda: b.read('messages', cid, text=self.input['outbound_text']),
                        lambda v: len(v['items']) == e['outbound_occurrences'], 'outbound persisted exactly once')
        message = result['items'][0]
        assert message['conversation_id'] == e['receiver_conversation']
        assert message['sender_id'] == e['outbound_sender']
        assert message['text'] == self.input['outbound_text']
        self.synced(message['id'], self.entity('peer'))
        u.wait(lambda: u.visible_message_count(message['id']) == e['outbound_occurrences'], 'outbound bubble')
        u.expect_text('chat.message', self.input['outbound_text'], id=message['id'])
        reply = b.call('send', sender_id=self.entity('peer'), conversation_id=cid, text=self.input['reply_text'])
        self.synced(reply['id'], self.entity('actor'))
        u.wait(lambda: u.visible_message_count(reply['id']) == e['reply_occurrences'], 'reply bubble')
        u.expect_text('chat.message', self.input['reply_text'], id=reply['id'])
        replies = b.read('messages', cid, text=self.input['reply_text'])['items']
        assert len(replies) == e['reply_occurrences']
        assert replies[0]['sender_id'] == e['reply_sender'] and replies[0]['text'] == self.input['reply_text']
        assert replies[0]['conversation_id'] == cid
        for text in (self.input['outbound_text'], self.input['reply_text']):
            assert len(b.read('messages', self.entity('D'), text=text)['items']) == e['unrelated_conversation_occurrences']
        if self.variant == 'group':
            u.back('home.ready')
            u.expect_text('conversation.preview', self.input['reply_text'], id=cid)

    def create_group(self):
        u, b, e, values = self.ui, self.bridge, self.expected, self.input
        u.click('home.create_group')
        u.element('create.ready')
        assert u.element('create.submit').is_enabled() == e['empty_form_submittable']
        u.input('create.name', values['name'])
        u.input('create.description', values['description'])
        u.set_toggle('create.visibility', values['public'])
        assert u.element('create.submit').is_enabled() == e['without_agreement_submittable']
        u.set_toggle('create.agreement', values['agreement_accepted'])
        u.click('create.submit')
        u.element('chat.ready')
        created = b.wait(lambda: b.read('created_groups', name=values['name']),
                         lambda v: len(v['items']) == e['created_group_count'], 'group created via UI')
        group = created['items'][0]
        self.runtime['created_group'] = {'id': group['id']}
        u.expect_text('chat.identity', group['id'])
        assert group['name'] == values['name'] and group['description'] == values['description']
        assert group['public'] == e['public'] and group['owner_id'] == e['owner']
        assert len(group['member_ids']) == e['member_count']
        assert group['member_ids'] == [e['only_member']]
        u.group_details()
        assert (u.optional('group.owner_controls') is not None) == e['owner_controls_visible']

    def application(self):
        u, b = self.ui, self.bridge
        e = self.expected['by_decision'][self.variant]
        gid, uid = self.entity('G'), self.entity('peer')
        baseline = b.read('group', gid)['member_ids']
        assert uid not in baseline
        self.probe('peer', 'send_message', self.expected['before_decision_can_send'])
        u.open_conversation(gid)
        u.group_details()
        u.click('group.applications')
        u.element('application.row', id=self.entity('R'))
        u.click('application.decision', id=self.entity('R'), decision=self.variant)
        self.state('application', 'R', status=e['application_status'])
        assert (b.read('application', self.entity('R'))['status'] == 'pending') == self.expected['application_pending_after_decision']
        members = self.bridge.wait(lambda: b.read('group', gid),
                                  lambda v: v['member_ids'].count(uid) == e['applicant_member_occurrences'], 'membership decision')['member_ids']
        assert set(members) == set(baseline) | ({uid} if e['applicant_can_send'] else set())
        self.probe('peer', 'send_message', e['applicant_can_send'])

    def probe(self, actor, operation, allowed):
        response = self.bridge.call('permission_probe', actor_id=self.entity(actor),
                                    group_id=self.entity('G'), application_id=self.entity('R'),
                                    operation_name=operation, input=self.input)
        assert response['allowed'] == allowed, f'Unexpected {actor} permission for {operation}'

    def permissions(self):
        u, b, e = self.ui, self.bridge, self.expected
        u.open_conversation(self.entity('G'))
        u.group_details()
        assert bool(u.collection('owner_controls')) == e['member_owner_controls_visible']
        before = b.read('permission_snapshot', self.entity('G'), application_id=self.entity('R'))
        self.probe('actor', self.variant, e['member_business_operation_allowed'])
        after = b.read('permission_snapshot', self.entity('G'), application_id=self.entity('R'))
        assert before == after, 'Rejected member action modified protected business state'
        self.probe('owner', e['positive_control_operation'], e['positive_control_allowed'])
        self.state('group', 'G', description=self.input['description'])

    def pin(self):
        u, e = self.ui, self.expected
        cid = self.input['target_group']
        private_before = u.collection('private_conversations')
        u.home()
        assert u.text('group.first') != cid
        u.open_conversation(cid)
        u.group_details()
        u.set_toggle('group.pin', e['pinned_after_enable'])
        self.state('conversation', 'G3', pinned=e['pinned_after_enable'])
        u.back('chat.ready')
        u.back('home.ready')
        u.expect_text('group.first', cid)
        assert (u.collection('private_conversations') != private_before) == e['private_section_changed']
        u.home()
        u.open_conversation(cid)
        u.group_details()
        assert u.toggle('group.pin') == e['pinned_after_reentry']
        u.set_toggle('group.pin', e['pinned_after_disable'])
        self.state('conversation', 'G3', pinned=e['pinned_after_disable'])
        u.back('chat.ready')
        u.back('home.ready')
        u.open_conversation(cid)
        u.group_details()
        assert u.toggle('group.pin') == e['pinned_after_disable']

    def categories(self):
        u, b, e = self.ui, self.bridge, self.expected
        aliases = e['categories']['all']
        before = {a: b.read('notification', self.entity(a))['read'] for a in aliases}
        u.click('home.interactions')
        for category, expected_aliases in e['categories'].items():
            u.click('interaction.category', category=category)
            assert u.collection('interactions') == {self.entity(a) for a in expected_aliases}
        after = {a: b.read('notification', self.entity(a))['read'] for a in aliases}
        assert (before != after) == e['switching_categories_marks_read']

    def run(self):
        flows = dict(zip((f'MSG-A{i:02}' for i in range(1, 9)),
                         (self.notification, self.hidden, self.messaging, self.create_group,
                          self.application, self.permissions, self.pin, self.categories)))
        flows[self.case_id]()
