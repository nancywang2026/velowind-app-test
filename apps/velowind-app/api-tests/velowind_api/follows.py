from .checks import require


def follow(http, actor, target_id):
    data = http.request("POST", "/api/v1/mobile/user-follows", token=actor.token,
                        body={"targetUserId": target_id})
    require(str(data.get("targetUserId")) == str(target_id), "Follow target mismatch")
    require(data.get("following") is True, "Follow not effective")
    return data
