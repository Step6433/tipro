from sqlalchemy import text
from app.core.errors import ApiError

async def validate_timezone(db, name):
    # Use the same PostgreSQL timezone database for validation, bucketing and filter boundaries.
    if name == 'UTC':
        return name
    if not name or len(name) > 100 or not await db.scalar(text('SELECT 1 FROM pg_timezone_names WHERE name=:name LIMIT 1'), {'name': name}):
        raise ApiError('Неизвестный часовой пояс.', 'INVALID_TIMEZONE', 400)
    return name
