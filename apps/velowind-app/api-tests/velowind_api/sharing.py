from .checks import card


class Sharing:
    def __init__(self, messages):
        self.messages = messages

    def post(self, peer_id, post_id, content):
        result = self.messages.send_text(peer_id, content, context={
            "contextType": "POST", "bizType": "POST", "bizId": post_id,
        })
        card(result, "POST", post_id)
        return result

    def activity(self, peer_id, activity_id, content):
        # ACTIVITY explicitly forbids bizType in the request contract.
        result = self.messages.send_text(peer_id, content, context={
            "contextType": "ACTIVITY", "bizId": activity_id,
        })
        card(result, "ACTIVITY", activity_id)
        return result
