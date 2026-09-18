"""Small helpers used by many routers."""
import math

from fastapi import HTTPException
from sqlalchemy import text


def paginate(db, select_sql, count_sql, params, page, per_page):
    """Run a list query one page at a time.

    select_sql: the SELECT ... WHERE ... ORDER BY ... part (without LIMIT)
    count_sql:  a SELECT COUNT(*) with the same WHERE, to know the total number of rows

    The endpoints limit per_page to 100 and page to 10,000, so a huge request
    gets a 422 instead of asking MySQL to skip billions of rows.
    """
    total = db.execute(text(count_sql), params).scalar()

    # LIMIT = how many rows, OFFSET = how many rows to skip.
    # Page 1 skips 0 rows, page 2 skips per_page rows, and so on.
    page_params = dict(params)
    page_params["limit"] = per_page
    page_params["offset"] = (page - 1) * per_page
    rows = db.execute(text(select_sql + " LIMIT :limit OFFSET :offset"), page_params).mappings().all()

    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": math.ceil(total / per_page),
        },
    }


def update_row(db, table, row_id, company_id, changes):
    """UPDATE one row with the given changes, only inside the user's company.

    It builds:  UPDATE leads SET status = :status, phone = :phone
                WHERE id = :id AND company_id = :company_id

    The column names come from our Pydantic models (extra fields are rejected),
    so the client can never choose which columns get updated. The values are
    sent separately as parameters, which protects against SQL injection.
    """
    if not changes:
        return

    set_parts = [f"{column} = :{column}" for column in changes]
    params = dict(changes)
    params["id"] = row_id
    params["company_id"] = company_id

    db.execute(
        text(f"UPDATE {table} SET {', '.join(set_parts)} WHERE id = :id AND company_id = :company_id"),
        params,
    )


def check_user_can_be_assigned(db, company_id, user_id):
    """Make sure user_id is an active user in the SAME company before we assign work to them."""
    found = db.execute(
        text("""
            SELECT id FROM users
            WHERE id = :id AND company_id = :company_id
              AND status = 'ACTIVE' AND deleted_at IS NULL
        """),
        {"id": user_id, "company_id": company_id},
    ).first()

    if found is None:
        # Same message whether the user is inactive or belongs to another company,
        # so nobody can use this to discover users of other companies.
        raise HTTPException(422, "The selected user does not exist in your company or is not active.")


def like_pattern(search):
    """Turn a search word into a LIKE pattern: john -> %john%

    % and _ are special characters in LIKE, so we escape them first.
    Otherwise searching for "%" would match everything.
    """
    search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{search}%"
