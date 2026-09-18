"""Saves a row in audit_logs for important actions (CREATE, UPDATE, DELETE, LOGIN, ...)."""
import json

from sqlalchemy import text

# These fields must never be written into the audit log.
SECRET_FIELDS = {"password", "password_hash", "token_hash", "token_id"}


def to_json(values):
    if values is None:
        return None
    safe_values = {key: value for key, value in dict(values).items() if key not in SECRET_FIELDS}
    # default=str turns dates and Decimals into text so json.dumps does not fail.
    return json.dumps(safe_values, default=str)


def save_audit_log(db, user, action, entity_type, entity_id, request=None,
                   old_values=None, new_values=None):
    """Call this INSIDE the same transaction as the change itself.

    Then the change and its audit log are saved together, or not at all.
    """
    ip_address = None
    user_agent = None
    if request is not None:
        if request.client:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "")[:512]

    db.execute(
        text("""
            INSERT INTO audit_logs
                (company_id, user_id, action, entity_type, entity_id,
                 old_values, new_values, ip_address, user_agent)
            VALUES
                (:company_id, :user_id, :action, :entity_type, :entity_id,
                 :old_values, :new_values, :ip_address, :user_agent)
        """),
        {
            "company_id": user["company_id"],
            "user_id": user["id"],
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_values": to_json(old_values),
            "new_values": to_json(new_values),
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
    )
